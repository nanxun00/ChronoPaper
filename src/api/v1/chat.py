import json
import asyncio
import queue
import threading
import uuid
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, Response
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.orm import Session

from src.api.deps import UserInDB, get_current_active_user, get_db
from src.models.base import SessionLocal
from src.services import literature_service
from src.services.chat import (
    build_assistant_message_metadata,
    build_llm_history,
    build_user_message_metadata,
    conversation_detail,
    create_conversation,
    delete_conversation,
    delete_message_turn,
    extract_bind_paper_id,
    get_conversation,
    list_conversations,
    persist_chat_turn,
    update_conversation_bindings,
    update_conversation_title,
)
from src.services.rag import HistoryManager
from src.services.rag.startup import startup
from src.services.memos import get_memory_service
from src.utils.logging_config import setup_logger

chat = APIRouter(prefix="/chat")
router = chat
logger = setup_logger("server-chat")
executor = ThreadPoolExecutor()

refs_pool: dict[str, dict] = {}


def _refs_set(user_id: str, res_id: str, refs) -> None:
    refs_pool.setdefault(user_id, {})[res_id] = refs


def _refs_get(user_id: str, res_id: str):
    return refs_pool.get(user_id, {}).get(res_id)


def _refs_pop(user_id: str, res_id: str):
    return refs_pool.get(user_id, {}).pop(res_id, None)


def _is_stream_enabled(meta: dict) -> bool:
    return meta.get("stream", True) is not False


def _should_emit_skill_progress(meta: dict) -> bool:
    """技能 codegen/脚本在流式正文开始前可能耗时较长，需先推送状态。"""
    if meta.get("codegen_approval_id"):
        return True
    mode = (meta.get("skill_mode") or "auto").strip().lower()
    if mode == "off":
        return False
    if meta.get("skill_run_scripts", True) is False and meta.get("skill_codegen", True) is False:
        return False
    return True


def _meta_for_persist(meta: dict) -> dict:
    clean = {**meta}
    cited = clean.get("cited_literature")
    if isinstance(cited, list):
        clean["cited_literature"] = [
            {k: v for k, v in item.items() if k != "full_text"}
            for item in cited
            if isinstance(item, dict)
        ]
    return clean


def _ensure_retrieval_db(meta: dict) -> dict:
    """启用检索但未指定知识库时，默认使用系统公共文献库（尊重用户「不使用」）。"""
    meta = dict(meta or {})
    if not meta.get("enable_retrieval"):
        return meta
    if meta.get("kbOptOut"):
        meta["db_name"] = None
        return meta
    if not meta.get("db_name") and startup.config.enable_knowledge_base:
        try:
            meta["db_name"] = startup.dbm.ensure_default_knowledge_base().metaname
        except Exception as exc:
            logger.warning("Could not resolve default knowledge base: %s", exc)
    return meta


def _skill_script_context(history_manager: HistoryManager, query: str) -> str:
    """供脚本规划从近期对话中提取 DOI 等标识。"""
    parts: list[str] = []
    for msg in (history_manager.messages or [])[-6:]:
        if msg.get("role") in ("user", "assistant"):
            content = (msg.get("content") or "").strip()
            if content:
                parts.append(content)
    if query.strip():
        parts.append(query.strip())
    return "\n\n".join(parts)


def _prepare_chat_query(
    query: str,
    history_manager: HistoryManager,
    meta: dict,
    literature_context: str,
    user_id: str,
    cur_res_id: str,
    *,
    on_progress=None,
) -> tuple[str, dict | None, str | None]:
    from src.services.skills import prepare_skill_turn

    skill_system, skill_info = prepare_skill_turn(
        query,
        meta,
        model=startup.model,
        user_id=user_id,
        run_id=cur_res_id,
        on_progress=on_progress,
        script_context=_skill_script_context(history_manager, query),
    )
    if skill_info.get("skill_id"):
        meta.update({k: v for k, v in skill_info.items() if v is not None})

    refs: dict | None = None
    if meta.get("enable_retrieval"):
        meta = _ensure_retrieval_db(meta)
        meta = {**meta, "user_id": user_id}
        new_query, refs = startup.retriever(query, history_manager.messages, meta)
    else:
        new_query = query

    if literature_context:
        new_query = f"{literature_context}\n\n用户问题：{new_query}"

    if skill_info.get("skill_id"):
        if refs is None:
            refs = {}
        refs["skill"] = skill_info
        _refs_set(user_id, cur_res_id, refs)
    elif refs is not None:
        _refs_set(user_id, cur_res_id, refs)

    return new_query, refs, skill_system


def _pending_codegen_approval(refs: dict | None) -> dict | None:
    if not refs:
        return None
    skill = refs.get("skill") or {}
    pending = skill.get("codegen_pending_approval")
    return pending if isinstance(pending, dict) else None


def _codegen_approval_message(pending: dict) -> str:
    review = pending.get("llm_review") or {}
    errors = pending.get("validation_errors") or []
    lines = [
        "生成脚本触发了静态高危规则，已暂停执行。",
        "",
        "**拦截项：**",
        *[f"- {e}" for e in errors],
        "",
        f"**LLM 安全审查：** {review.get('summary') or '—'}",
    ]
    risks = review.get("risks") or []
    if risks:
        lines.extend(["", "**潜在风险：**", *[f"- {r}" for r in risks]])
    lines.extend(["", "请在下方面板选择 **放行执行** 或 **拒绝**。"])
    return "\n".join(lines)


def _inject_skill_system(messages: list, skill_system: str | None) -> list:
    parts: list[str] = []
    global_prompt = (startup.config.get("chat_system_prompt") or "").strip()
    if global_prompt:
        parts.append(global_prompt)
    if skill_system and skill_system.strip():
        parts.append(skill_system.strip())
    if not parts:
        return messages
    combined = "\n\n".join(parts)
    return [{"role": "system", "content": combined}, *messages]


def _message_to_response_content(message) -> tuple[dict, str]:
    response_content = {"reasoning_content": "", "content": ""}
    reasoning = getattr(message, "reasoning_content", None)
    if reasoning:
        response_content["reasoning_content"] = reasoning
    content = getattr(message, "content", None)
    if content is None:
        content = str(message)
    response_content["content"] = content or ""
    return response_content, response_content["content"]


def _should_use_skill_agent(meta: dict, skill_system: str | None, refs: dict | None) -> bool:
    if meta.get("skill_agent", True) is False:
        return False
    if not skill_system:
        return False
    if _pending_codegen_approval(refs):
        return False
    skill = (refs or {}).get("skill") or {}
    if not skill.get("skill_id"):
        return False
    if (meta.get("skill_mode") or "auto").strip().lower() == "off":
        return False
    return True


def _will_generate_image(query: str, meta: dict, user_id: str, conv_id: str) -> bool:
    from src.services.image_gen.service import is_confirm_text, resolve_pending

    pending = resolve_pending(user_id, conv_id, meta)
    if not pending:
        return False
    if meta.get("image_gen_confirm") is True:
        return True
    return is_confirm_text(query)


def _maybe_attach_generated_document(
    *,
    query: str,
    assistant_content: str,
    meta: dict,
    model,
    user_id: str,
    cur_res_id: str,
    refs: dict | None,
) -> dict | None:
    if not meta.get("document_gen_mode"):
        return refs
    if not (assistant_content or "").strip():
        return refs

    from src.services.document_gen.service import try_generate_document_from_turn

    artifact = try_generate_document_from_turn(
        query=query,
        assistant_content=assistant_content,
        model=model,
    )
    if not artifact:
        return refs

    merged = dict(refs or {})
    merged["document"] = artifact
    _refs_set(user_id, cur_res_id, merged)
    return merged


def _get_memory_tools(enable_memory: bool) -> list:
    """根据 enable_memory 开关获取 MemOS 工具 Schema。

    开关关闭（硬隔离机制，禁止仅靠提示词约束）：
    业务工具管理器不加载 MemOS 全套 MCP 工具，
    传递给大模型的 tools 数组不含记忆相关函数，
    所有模型完全感知不到记忆读写、检索能力，杜绝私自调用记忆。

    开关开启：加载云端 MemOS 全部 MCP 工具。
    开关逻辑与联网检索 Hosted MCP 保持统一代码架构、统一分支判断逻辑。
    记忆模块无任何模型绑定逻辑，所有支持 Function Calling 的模型均可统一使用。
    """
    if not enable_memory:
        return []
    memos_service = get_memory_service()
    if not memos_service.is_enabled:
        return []
    return memos_service.get_tools_schema(enable_memory=True)


def _get_web_search_tools(enable_web_search: bool) -> list:
    """根据 enable_web_search 开关获取联网搜索工具 Schema。"""
    if not enable_web_search:
        return []
    from src.services.web_search import get_web_search_service
    web_search_service = get_web_search_service()
    if not web_search_service.is_enabled:
        return []
    return web_search_service.get_tools_schema(enable_web_search=True)


def _apply_image_gen_result(
    *,
    img: dict,
    query: str,
    history_manager: HistoryManager,
    user_id: str,
    cur_res_id: str,
    persist_turn,
) -> tuple[dict, list, dict | None]:
    history_manager.add_user(query)
    refs = img.get("refs")
    if refs:
        _refs_set(user_id, cur_res_id, refs)
    updated_history = persist_turn(
        img.get("content") or "",
        reasoning_content="",
        refs=refs,
        assistant_status=img.get("status") or "finished",
        assistant_images=img.get("images") or [],
    )
    response_content = {"reasoning_content": "", "content": img.get("content") or ""}
    return response_content, updated_history, refs


def _run_skill_agent(model, messages: list, skill_id: str) -> str:
    from src.services.skills.agent import run_skill_agent
    from src.services.skills.registry import get_skill_registry

    record = get_skill_registry().get(skill_id)
    if not record:
        return ""
    return run_skill_agent(model, messages, record.path).content


_PREPARE_DONE = object()


def _start_prepare_worker(
    query: str,
    history_manager: HistoryManager,
    meta: dict,
    literature_context: str,
    user_id: str,
    cur_res_id: str,
) -> tuple[queue.Queue, threading.Thread, dict, dict]:
    progress_queue: queue.Queue = queue.Queue()
    result_box: dict = {}
    error_box: dict = {}

    def worker() -> None:
        def on_progress(event) -> None:
            progress_queue.put(event)

        try:
            result_box["result"] = _prepare_chat_query(
                query,
                history_manager,
                meta,
                literature_context,
                user_id,
                cur_res_id,
                on_progress=on_progress,
            )
        except Exception as exc:
            error_box["error"] = exc
        finally:
            progress_queue.put(_PREPARE_DONE)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return progress_queue, thread, result_box, error_box


def _drain_codegen_progress(progress_queue: queue.Queue, thread: threading.Thread):
    while True:
        try:
            item = progress_queue.get(timeout=0.25)
        except queue.Empty:
            if not thread.is_alive() and progress_queue.empty():
                break
            continue
        if item is _PREPARE_DONE:
            break
        yield item


def _resolve_conversation(
    db: Session,
    user_id: str,
    conv_id: str | None,
) -> str:
    if conv_id:
        conv = get_conversation(db, user_id, conv_id)
        if not conv:
            raise HTTPException(status_code=404, detail="会话不存在或无权访问")
        return conv_id
    conv = create_conversation(db, user_id)
    return conv.conv_id


@chat.get("/conversations")
def list_user_conversations(
    current_user: UserInDB = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    rows = list_conversations(db, current_user.userid)
    return {"conversations": [row.to_dict() for row in rows]}


@chat.post("/conversations")
def create_user_conversation(
    body: dict = Body(default={}),
    current_user: UserInDB = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    conv = create_conversation(
        db,
        current_user.userid,
        title=body.get("title") or "新对话",
        bind_paper_id=body.get("bind_paper_id"),
        bind_doc_id=body.get("bind_doc_id"),
        system_prompt=body.get("system_prompt"),
    )
    return conv.to_dict()


@chat.get("/conversations/{conv_id}")
def get_user_conversation_detail(
    conv_id: str,
    message_limit: int = Query(8, ge=1, le=100),
    before_msg_id: str | None = Query(None),
    current_user: UserInDB = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    detail = conversation_detail(
        db,
        current_user.userid,
        conv_id,
        message_limit=message_limit,
        before_msg_id=before_msg_id,
    )
    if not detail:
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")
    return detail


@chat.patch("/conversations/{conv_id}")
def patch_user_conversation(
    conv_id: str,
    body: dict = Body(...),
    current_user: UserInDB = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    conv = None
    if "title" in body:
        conv = update_conversation_title(db, current_user.userid, conv_id, body.get("title") or "")
    if "bind_paper_id" in body or "bind_doc_id" in body:
        conv = update_conversation_bindings(
            db,
            current_user.userid,
            conv_id,
            bind_paper_id=body.get("bind_paper_id") if "bind_paper_id" in body else None,
            bind_doc_id=body.get("bind_doc_id") if "bind_doc_id" in body else None,
        )
    if conv is None:
        conv = get_conversation(db, current_user.userid, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")
    return conv.to_dict()


@chat.delete("/conversations/{conv_id}")
def delete_user_conversation(
    conv_id: str,
    current_user: UserInDB = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if not delete_conversation(db, current_user.userid, conv_id):
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")
    return {"ok": True}


@chat.delete("/conversations/{conv_id}/turns/{assistant_msg_id}")
def delete_conversation_turn(
    conv_id: str,
    assistant_msg_id: str,
    current_user: UserInDB = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    detail = delete_message_turn(db, current_user.userid, conv_id, assistant_msg_id)
    if not detail:
        raise HTTPException(status_code=404, detail="消息不存在或无权访问")
    return detail


@chat.get("/")
async def chat_get():
    return "Chat Get!"


@chat.post("/")
def chat_post(
    query: str = Body(...),
    meta: dict = Body(None),
    history: list = Body(default=[]),
    cur_res_id: str = Body(...),
    conv_id: str | None = Body(None),
    user_msg_id: str | None = Body(None),
    current_user: UserInDB = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    meta = meta or {}
    meta = _ensure_retrieval_db(meta)
    user_id = current_user.userid
    conv_id = _resolve_conversation(db, user_id, conv_id)
    user_msg_id = user_msg_id or f"msg-{uuid.uuid4().hex}"

    cited_raw = meta.get("cited_literature") or []
    literature_context = ""
    if cited_raw:
        enriched, literature_context = literature_service.prepare_cited_literature_for_chat(
            db, cited_raw, user_id=user_id
        )
        meta = {**meta, "cited_literature": enriched}

    db_history = build_llm_history(db, conv_id)
    history_manager = HistoryManager(db_history if conv_id else history)

    def make_chunk(content, status, history=None, refs=None):
        payload = {
            "response": content,
            "history": history,
            "model_name": startup.config.model_name,
            "status": status,
            "meta": meta,
            "conv_id": conv_id,
        }
        if refs is not None:
            payload["refs"] = refs
        return json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n"

    def persist_turn(
        assistant_content: str,
        reasoning_content: str = "",
        refs=None,
        *,
        assistant_status: str = "finished",
        assistant_images: list | None = None,
    ) -> list[dict]:
        user_meta = build_user_message_metadata(
            ui_msg_id=user_msg_id,
            images=meta.get("images") or [],
            citations=cited_raw,
        )
        assistant_meta = build_assistant_message_metadata(
            ui_msg_id=cur_res_id,
            reasoning_content=reasoning_content,
            refs=refs,
            model_name=startup.config.model_name,
            status=assistant_status,
            chat_meta=_meta_for_persist(meta),
            images=assistant_images,
        )
        persist_chat_turn(
            db,
            user_id,
            conv_id,
            user_msg_id=user_msg_id,
            assistant_msg_id=cur_res_id,
            user_content=query,
            assistant_content=assistant_content,
            user_metadata=user_meta,
            assistant_metadata=assistant_meta,
            bind_paper_id=extract_bind_paper_id(cited_raw),
        )
        return build_llm_history(db, conv_id)

    use_stream = _is_stream_enabled(meta)

    from src.services.image_gen import try_handle_image_generation

    if _will_generate_image(query, meta, user_id, conv_id):
        meta = {**meta, "image_gen_confirm": True}

    img_turn = try_handle_image_generation(
        query=query,
        meta=meta,
        user_id=user_id,
        conv_id=conv_id,
        model=startup.model,
    )

    if not use_stream:
        if img_turn is not None:
            response_content, updated_history, refs = _apply_image_gen_result(
                img=img_turn,
                query=query,
                history_manager=history_manager,
                user_id=user_id,
                cur_res_id=cur_res_id,
                persist_turn=persist_turn,
            )
            payload = {
                "response": response_content,
                "history": updated_history,
                "model_name": startup.config.model_name,
                "status": img_turn.get("status") or "finished",
                "meta": meta,
                "conv_id": conv_id,
                "refs": refs,
            }
            if img_turn.get("images"):
                payload["response"] = {**response_content, "images": img_turn["images"]}
            return Response(
                content=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                media_type="application/json",
            )

        new_query, refs, skill_system = _prepare_chat_query(
            query, history_manager, meta, literature_context, user_id, cur_res_id
        )
        pending = _pending_codegen_approval(refs)
        if pending:
            summary = _codegen_approval_message(pending)
            payload = {
                "response": {"content": summary, "codegen_approval": pending},
                "history": history_manager.messages,
                "model_name": startup.config.model_name,
                "status": "skill_code_approval",
                "meta": meta,
                "conv_id": conv_id,
                "refs": refs,
            }
            return Response(
                content=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                media_type="application/json",
            )
        messages = history_manager.get_history_with_msg(new_query, max_rounds=meta.get("history_round"))
        messages = _inject_skill_system(messages, skill_system)
        history_manager.add_user(query)
        skill_id = (refs or {}).get("skill", {}).get("skill_id")
        if _should_use_skill_agent(meta, skill_system, refs) and skill_id:
            content = _run_skill_agent(startup.model, messages, skill_id)
            response_content = {"reasoning_content": "", "content": content}
        else:
            memory_tools = _get_memory_tools(meta.get("enable_memory", False))
            web_search_tools = _get_web_search_tools(meta.get("enable_web_search", False))
            all_tools = (memory_tools or []) + (web_search_tools or [])

            # 注入系统提示词强制引导模型直接调用工具
            system_instructions = []
            if web_search_tools:
                system_instructions.append(
                    "【强制指令】联网搜索功能已开启。当用户询问实时信息时，你必须立即调用 `bing_search` 工具。"
                )
            if memory_tools:
                system_instructions.append(
                    "【强制指令】记忆功能已开启。当用户提到个人信息时，请调用 `add_message` 存入记忆。"
                )

            if system_instructions:
                messages = [{"role": "system", "content": "\n".join(system_instructions)}] + messages

            message = startup.model.predict(
                messages, stream=False, tools=all_tools or None,
                user_id=user_id, session_id=conv_id,
            )
            response_content, content = _message_to_response_content(message)
        refs = _refs_get(user_id, cur_res_id)
        if meta.get("document_gen_mode") and content.strip():
            refs = _maybe_attach_generated_document(
                query=query,
                assistant_content=content,
                meta=meta,
                model=startup.model,
                user_id=user_id,
                cur_res_id=cur_res_id,
                refs=refs,
            )
        updated_history = persist_turn(
            content,
            reasoning_content=response_content.get("reasoning_content") or "",
            refs=refs,
        )
        payload = {
            "response": response_content,
            "history": updated_history,
            "model_name": startup.config.model_name,
            "status": "finished",
            "meta": meta,
            "conv_id": conv_id,
            "refs": refs,
        }
        return Response(
            content=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            media_type="application/json",
        )

    def generate_response():
        stream_meta = dict(meta)
        if _will_generate_image(query, stream_meta, user_id, conv_id):
            stream_meta["image_gen_confirm"] = True
            yield make_chunk("", "image_generating", history=None)

        img_turn = try_handle_image_generation(
            query=query,
            meta=stream_meta,
            user_id=user_id,
            conv_id=conv_id,
            model=startup.model,
        )
        if img_turn is not None:
            response_content, updated_history, refs = _apply_image_gen_result(
                img=img_turn,
                query=query,
                history_manager=history_manager,
                user_id=user_id,
                cur_res_id=cur_res_id,
                persist_turn=persist_turn,
            )
            if img_turn.get("images"):
                response_content["images"] = img_turn["images"]
            yield make_chunk(
                response_content,
                img_turn.get("status") or "finished",
                history=updated_history,
                refs=refs,
            )
            return

        use_skill_progress = _should_emit_skill_progress(meta)
        if meta.get("enable_retrieval"):
            yield make_chunk("", "searching", history=None)
        elif use_skill_progress:
            yield make_chunk("", "skill_running", history=None)

        if use_skill_progress:
            progress_queue, worker, result_box, error_box = _start_prepare_worker(
                query, history_manager, meta, literature_context, user_id, cur_res_id
            )
            for event in _drain_codegen_progress(progress_queue, worker):
                payload = event.to_dict() if hasattr(event, "to_dict") else dict(event)
                yield make_chunk({"skill_progress": payload}, "skill_running", history=None)
            worker.join(timeout=300)
            if error_box.get("error"):
                raise error_box["error"]
            new_query, refs, skill_system = result_box["result"]
        else:
            new_query, refs, skill_system = _prepare_chat_query(
                query, history_manager, meta, literature_context, user_id, cur_res_id
            )
        pending = _pending_codegen_approval(refs)
        if pending:
            summary = _codegen_approval_message(pending)
            yield make_chunk(
                {"content": summary, "codegen_approval": pending},
                "skill_code_approval",
                refs=refs,
            )
            return

        messages = history_manager.get_history_with_msg(new_query, max_rounds=meta.get("history_round"))
        messages = _inject_skill_system(messages, skill_system)
        history_manager.add_user(query)
        logger.debug(f"Web history: {history_manager.messages}")

        content = ""
        response_content = {"reasoning_content": "", "content": ""}
        skill_id = (refs or {}).get("skill", {}).get("skill_id")
        use_agent = _should_use_skill_agent(meta, skill_system, refs) and skill_id
        # 与前端「流式输出」开关一致：关则整段返回，开则逐 token 推送 loading
        llm_stream = use_stream

        if use_agent:
            from src.services.skills.agent import iter_skill_agent
            from src.services.skills.registry import get_skill_registry

            yield make_chunk("", "skill_agent", history=None)
            record = get_skill_registry().get(skill_id)
            agent_status = "skill_agent"
            agent_streamed = False
            if record:
                for event in iter_skill_agent(
                    startup.model, messages, record.path, stream=llm_stream
                ):
                    if event.kind == "tool_step":
                        if agent_status != "skill_agent":
                            agent_status = "skill_agent"
                            yield make_chunk("", "skill_agent", history=None)
                        continue
                    if event.kind == "token":
                        agent_streamed = True
                        content = event.content
                        response_content["content"] = content
                        agent_status = "loading"
                        chunk = make_chunk(
                            response_content,
                            "loading",
                            history=history_manager.update_ai(content),
                        )
                        yield chunk
                    elif event.kind == "done" and event.result is not None:
                        content = event.result.content
                        response_content["content"] = content
                        if not agent_streamed and content:
                            chunk = make_chunk(
                                response_content,
                                "loading",
                                history=history_manager.update_ai(content),
                            )
                            yield chunk
            else:
                content = _run_skill_agent(startup.model, messages, skill_id)
                response_content["content"] = content
                chunk = make_chunk(
                    response_content,
                    "loading",
                    history=history_manager.update_ai(content),
                )
                yield chunk
        else:
            # 如果启用了记忆工具或联网搜索工具，使用非流式调用（Function Calling 需要完整响应处理工具调用）
            memory_tools = _get_memory_tools(meta.get("enable_memory", False))
            web_search_tools = _get_web_search_tools(meta.get("enable_web_search", False))
            all_tools = (memory_tools or []) + (web_search_tools or [])

            if all_tools:
                # 注入系统提示词强制引导模型直接调用工具，禁止废话
                system_instructions = []
                if web_search_tools:
                    system_instructions.append(
                        "【强制指令】联网搜索功能已开启。当用户询问实时信息（如：今天的新闻、最新的论文、当前日期等）时，"
                        "你必须立即调用 `bing_search` 工具。禁止回答你无法获取实时信息，禁止在调用前进行任何解释。"
                    )
                if memory_tools:
                    system_instructions.append(
                        "【强制指令】记忆功能已开启。当用户提到个人信息、偏好或研究背景时，请调用 `add_message` 存入记忆。"
                    )
                
                if system_instructions:
                    # 统一使用 dict 格式，确保与 history 格式一致
                    messages = [{"role": "system", "content": "\n".join(system_instructions)}] + messages

                # 使用非流式调用，支持工具调用循环
                message = startup.model.predict(
                    messages, stream=False, tools=all_tools,
                    user_id=user_id, session_id=conv_id,
                )
                response_content, content = _message_to_response_content(message)
                # 生成一个包含完整内容的块
                chunk = make_chunk(response_content, "loading", history=history_manager.update_ai(content))
                yield chunk
            else:
                # 正常的流式调用
                for delta in startup.model.predict(messages, stream=llm_stream):
                    if not delta.content:
                        continue
                    if startup.model.model_name in ("deepseek-r1:32b", "deepseek-r1:14b"):
                        if hasattr(delta, "is_full") and delta.is_full:
                            if hasattr(delta, "reasoning_content"):
                                response_content["reasoning_content"] = delta.reasoning_content
                            response_content["content"] = delta.content
                            content = delta.content
                        else:
                            if hasattr(delta, "reasoning_content"):
                                response_content["reasoning_content"] += delta.reasoning_content
                            response_content["content"] += delta.content
                            content += delta.content
                    else:
                        if hasattr(delta, "is_full") and delta.is_full:
                            response_content["content"] = delta.content
                            content = delta.content
                        else:
                            response_content["content"] += delta.content
                            content += delta.content

                    chunk = make_chunk(response_content, "loading", history=history_manager.update_ai(content))
                    yield chunk

        refs = _refs_get(user_id, cur_res_id)
        if meta.get("document_gen_mode") and content.strip():
            yield make_chunk("", "document_generating", history=None)
            refs = _maybe_attach_generated_document(
                query=query,
                assistant_content=content,
                meta=meta,
                model=startup.model,
                user_id=user_id,
                cur_res_id=cur_res_id,
                refs=refs,
            )
        updated_history = persist_turn(
            content,
            reasoning_content=response_content.get("reasoning_content") or "",
            refs=refs,
        )
        yield make_chunk(response_content, "finished", history=updated_history, refs=refs)

    return StreamingResponse(generate_response(), media_type="application/json")


@chat.post("/call")
async def call(
    query: str = Body(...),
    meta: dict = Body(None),
    current_user: UserInDB = Depends(get_current_active_user),
):
    async def predict_async(query_text):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(executor, startup.model.predict, query_text)

    response = await predict_async(query)
    logger.debug({"query": query, "response": response.content})
    return {"response": response.content}


@chat.get("/refs")
def get_refs(
    cur_res_id: str,
    current_user: UserInDB = Depends(get_current_active_user),
):
    refs = _refs_get(current_user.userid, cur_res_id)
    if refs is not None:
        _refs_pop(current_user.userid, cur_res_id)
    return {"refs": refs}


@chat.get("/memories")
def get_long_term_memories(
    current_user: UserInDB = Depends(get_current_active_user),
):
    """获取当前用户的所有长期记忆（全局，不按会话分割）。"""
    memos_service = get_memory_service()
    if not memos_service.is_enabled:
        return {"ok": False, "error": "记忆功能未启用", "memories": []}

    result = memos_service.list_all_memories(
        user_id=current_user.userid,
        top_k=100,
        enable_memory=True,
    )
    return result
