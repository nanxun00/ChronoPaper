import json
import asyncio
import uuid
from fastapi import APIRouter, Body, Depends, HTTPException
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


def _prepare_chat_query(
    query: str,
    history_manager: HistoryManager,
    meta: dict,
    literature_context: str,
    user_id: str,
    cur_res_id: str,
) -> str:
    if meta.get("enable_retrieval"):
        new_query, refs = startup.retriever(query, history_manager.messages, meta)
        _refs_set(user_id, cur_res_id, refs)
    else:
        new_query = query
    if literature_context:
        new_query = f"{literature_context}\n\n用户问题：{new_query}"
    return new_query


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
    current_user: UserInDB = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    detail = conversation_detail(db, current_user.userid, conv_id)
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

    def make_chunk(content, status, history=None):
        return json.dumps(
            {
                "response": content,
                "history": history,
                "model_name": startup.config.model_name,
                "status": status,
                "meta": meta,
                "conv_id": conv_id,
            },
            ensure_ascii=False,
        ).encode("utf-8") + b"\n"

    def persist_turn(
        assistant_content: str,
        reasoning_content: str = "",
        refs=None,
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
            status="finished",
            chat_meta=_meta_for_persist(meta),
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

    if not use_stream:
        new_query = _prepare_chat_query(
            query, history_manager, meta, literature_context, user_id, cur_res_id
        )
        messages = history_manager.get_history_with_msg(new_query, max_rounds=meta.get("history_round"))
        history_manager.add_user(query)
        message = startup.model.predict(messages, stream=False)
        response_content, content = _message_to_response_content(message)
        refs = _refs_get(user_id, cur_res_id)
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
        }
        return Response(
            content=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            media_type="application/json",
        )

    def generate_response():
        if meta.get("enable_retrieval"):
            yield make_chunk("", "searching", history=None)

        new_query = _prepare_chat_query(
            query, history_manager, meta, literature_context, user_id, cur_res_id
        )
        messages = history_manager.get_history_with_msg(new_query, max_rounds=meta.get("history_round"))
        history_manager.add_user(query)
        logger.debug(f"Web history: {history_manager.messages}")

        content = ""
        response_content = {"reasoning_content": "", "content": ""}
        for delta in startup.model.predict(messages, stream=True):
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
        updated_history = persist_turn(
            content,
            reasoning_content=response_content.get("reasoning_content") or "",
            refs=refs,
        )
        yield make_chunk(response_content, "finished", history=updated_history)

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
    refs = _refs_pop(current_user.userid, cur_res_id)
    return {"refs": refs}
