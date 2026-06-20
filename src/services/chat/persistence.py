"""聊天会话持久化与用户隔离。"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from src.models.chat import ChatConversation, ChatMessage
from src.services.rag.startup import startup


def _new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex}"


def _touch_conversation(conv: ChatConversation) -> None:
    conv.last_active_at = datetime.utcnow()


def create_conversation(
    db: Session,
    user_id: str,
    *,
    title: str = "新对话",
    bind_paper_id: str | None = None,
    bind_doc_id: str | None = None,
    system_prompt: str | None = None,
) -> ChatConversation:
    model_name = startup.config.model_name if startup.config else ""
    conv = ChatConversation(
        conv_id=_new_id("conv-"),
        user_id=user_id,
        title=title or "新对话",
        bind_paper_id=bind_paper_id,
        bind_doc_id=bind_doc_id,
        model_name=model_name,
        system_prompt=system_prompt,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def get_conversation(db: Session, user_id: str, conv_id: str) -> ChatConversation | None:
    return (
        db.query(ChatConversation)
        .filter(ChatConversation.conv_id == conv_id, ChatConversation.user_id == user_id)
        .first()
    )


def list_conversations(db: Session, user_id: str, *, limit: int = 100) -> list[ChatConversation]:
    return (
        db.query(ChatConversation)
        .filter(ChatConversation.user_id == user_id)
        .order_by(ChatConversation.last_active_at.desc())
        .limit(limit)
        .all()
    )


def update_conversation_title(db: Session, user_id: str, conv_id: str, title: str) -> ChatConversation | None:
    conv = get_conversation(db, user_id, conv_id)
    if not conv:
        return None
    conv.title = (title or "").strip() or conv.title
    _touch_conversation(conv)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def update_conversation_bindings(
    db: Session,
    user_id: str,
    conv_id: str,
    *,
    bind_paper_id: str | None = None,
    bind_doc_id: str | None = None,
) -> ChatConversation | None:
    conv = get_conversation(db, user_id, conv_id)
    if not conv:
        return None
    if bind_paper_id is not None:
        conv.bind_paper_id = bind_paper_id or None
    if bind_doc_id is not None:
        conv.bind_doc_id = bind_doc_id or None
    _touch_conversation(conv)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def delete_conversation(db: Session, user_id: str, conv_id: str) -> bool:
    conv = get_conversation(db, user_id, conv_id)
    if not conv:
        return False
    db.query(ChatMessage).filter(ChatMessage.conv_id == conv_id).delete(synchronize_session=False)
    db.delete(conv)
    db.commit()
    return True


def list_messages(db: Session, conv_id: str) -> list[ChatMessage]:
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.conv_id == conv_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )


def count_ui_messages(db: Session, conv_id: str) -> int:
    return (
        db.query(ChatMessage)
        .filter(
            ChatMessage.conv_id == conv_id,
            ChatMessage.role.in_(("user", "assistant")),
        )
        .count()
    )


def _resolve_message_anchor(db: Session, conv_id: str, msg_id: str) -> ChatMessage | None:
    row = (
        db.query(ChatMessage)
        .filter(ChatMessage.msg_id == msg_id, ChatMessage.conv_id == conv_id)
        .first()
    )
    if row:
        return row
    rows = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.conv_id == conv_id,
            ChatMessage.role.in_(("user", "assistant")),
        )
        .order_by(ChatMessage.created_at.desc())
        .limit(500)
        .all()
    )
    for row in rows:
        meta = row.metadata_json or {}
        if meta.get("ui_msg_id") == msg_id:
            return row
    return None


def list_messages_page(
    db: Session,
    conv_id: str,
    *,
    limit: int = 30,
    before_msg_id: str | None = None,
) -> list[ChatMessage]:
    """按时间正序返回最近 limit 条 UI 消息；before_msg_id 用于向上翻页。"""
    q = db.query(ChatMessage).filter(
        ChatMessage.conv_id == conv_id,
        ChatMessage.role.in_(("user", "assistant")),
    )
    if before_msg_id:
        anchor = _resolve_message_anchor(db, conv_id, before_msg_id)
        if anchor and anchor.created_at:
            q = q.filter(ChatMessage.created_at < anchor.created_at)
    rows = q.order_by(ChatMessage.created_at.desc()).limit(limit).all()
    return list(reversed(rows))


def _ui_msg_id(row: ChatMessage) -> str:
    meta = row.metadata_json or {}
    return meta.get("ui_msg_id") or row.msg_id


def _messages_has_older(db: Session, conv_id: str, oldest_row: ChatMessage | None) -> bool:
    if not oldest_row or not oldest_row.created_at:
        return False
    return (
        db.query(ChatMessage)
        .filter(
            ChatMessage.conv_id == conv_id,
            ChatMessage.role.in_(("user", "assistant")),
            ChatMessage.created_at < oldest_row.created_at,
        )
        .count()
        > 0
    )


def build_llm_history(db: Session, conv_id: str) -> list[dict]:
    """构建发给大模型的 history（user/assistant 纯文本）。"""
    rows = list_messages(db, conv_id)
    history: list[dict] = []
    for row in rows:
        if row.role not in ("user", "assistant"):
            continue
        history.append({"role": row.role, "content": row.content or ""})
    return history


def _slim_refs(refs) -> dict | None:
    """列表加载时剥离检索正文等大字段，避免响应体过大。"""
    if not refs or not isinstance(refs, dict):
        return None
    out: dict = {}
    skill = refs.get("skill")
    if isinstance(skill, dict):
        out["skill"] = {
            "skill_id": skill.get("skill_id"),
            "skill_name": skill.get("skill_name"),
            "artifacts": skill.get("artifacts") or [],
        }
    kb = refs.get("knowledge_base")
    if isinstance(kb, dict) and isinstance(kb.get("results"), list):
        slim_results = []
        for item in kb["results"][:12]:
            if not isinstance(item, dict):
                continue
            entity = item.get("entity") if isinstance(item.get("entity"), dict) else {}
            slim_results.append(
                {
                    "id": item.get("id"),
                    "distance": item.get("distance"),
                    "rerank_score": item.get("rerank_score"),
                    "file": item.get("file"),
                    "entity": {
                        "paper_id": entity.get("paper_id"),
                        "page_num": entity.get("page_num"),
                        "text": "",
                    },
                }
            )
        out["knowledge_base"] = {"results": slim_results}
    for key in ("entities", "triples"):
        if refs.get(key):
            out[key] = refs[key]
    return out or None


def _ui_message_from_row(row: ChatMessage, *, slim: bool = False) -> dict:
    meta = row.metadata_json or {}
    content = row.content or ""
    if row.role == "user":
        return {
            "id": meta.get("ui_msg_id") or row.msg_id,
            "role": "sent",
            "text": content,
            "images": meta.get("images") or [],
            "citations": meta.get("citations") or [],
            "status": "finished",
        }
    ponder = meta.get("reasoning_content") or ""
    refs = meta.get("refs")
    if slim:
        ponder = ""
        refs = _slim_refs(refs)
    return {
        "id": meta.get("ui_msg_id") or row.msg_id,
        "role": "received",
        "text": content,
        "ponder": ponder,
        "refs": refs,
        "model_name": meta.get("model_name"),
        "status": meta.get("status") or "finished",
        "meta": meta.get("chat_meta") or {},
    }


def conversation_detail(
    db: Session,
    user_id: str,
    conv_id: str,
    *,
    message_limit: int | None = 8,
    before_msg_id: str | None = None,
) -> dict | None:
    conv = get_conversation(db, user_id, conv_id)
    if not conv:
        return None

    use_slim = message_limit is not None
    total_messages = count_ui_messages(db, conv_id) if not before_msg_id else None
    if message_limit is None:
        rows = [row for row in list_messages(db, conv_id) if row.role in ("user", "assistant")]
        messages_has_more = False
    else:
        limit = max(1, min(int(message_limit), 100))
        rows = list_messages_page(db, conv_id, limit=limit, before_msg_id=before_msg_id)
        messages_has_more = _messages_has_older(db, conv_id, rows[0] if rows else None)

    messages = [_ui_message_from_row(row, slim=use_slim) for row in rows]
    oldest_msg_id = _ui_msg_id(rows[0]) if rows else None

    return {
        **conv.to_dict(),
        "messages": messages,
        "history": [],
        "messages_total": total_messages,
        "messages_has_more": messages_has_more,
        "oldest_msg_id": oldest_msg_id,
    }


def _upsert_message(
    db: Session,
    *,
    msg_id: str,
    conv_id: str,
    role: str,
    content: str,
    metadata: dict | None = None,
    total_tokens: int = 0,
) -> ChatMessage:
    row = db.query(ChatMessage).filter(ChatMessage.msg_id == msg_id).first()
    if row:
        row.content = content
        row.metadata_json = metadata or {}
        row.total_tokens = total_tokens
        db.add(row)
        return row
    row = ChatMessage(
        msg_id=msg_id,
        conv_id=conv_id,
        role=role,
        content=content,
        metadata_json=metadata or {},
        total_tokens=total_tokens,
    )
    db.add(row)
    return row


def build_user_message_metadata(
    *,
    ui_msg_id: str,
    images: list | None = None,
    citations: list | None = None,
) -> dict:
    meta: dict = {"ui_msg_id": ui_msg_id}
    if images:
        meta["images"] = images
    if citations:
        meta["citations"] = citations
        first = citations[0]
        paper_id = first.get("arxiv_id") or first.get("paper_id")
        if paper_id:
            meta["source_type"] = first.get("visibility") or "public_paper"
            meta["paper_id"] = paper_id
    return meta


def build_assistant_message_metadata(
    *,
    ui_msg_id: str,
    reasoning_content: str = "",
    refs=None,
    model_name: str = "",
    status: str = "finished",
    chat_meta: dict | None = None,
) -> dict:
    meta: dict = {"ui_msg_id": ui_msg_id, "status": status}
    if reasoning_content:
        meta["reasoning_content"] = reasoning_content
    if refs is not None:
        meta["refs"] = refs
    if model_name:
        meta["model_name"] = model_name
    if chat_meta:
        meta["chat_meta"] = chat_meta
    return meta


def extract_bind_paper_id(citations: list | None) -> str | None:
    if not citations:
        return None
    first = citations[0]
    return first.get("arxiv_id") or first.get("paper_id") or None


def delete_message_turn(
    db: Session,
    user_id: str,
    conv_id: str,
    assistant_msg_id: str,
) -> dict | None:
    """删除一轮问答（assistant 及其前一条 user 消息）。"""
    conv = get_conversation(db, user_id, conv_id)
    if not conv:
        return None

    rows = list_messages(db, conv_id)
    target_idx = None
    for i, row in enumerate(rows):
        if row.role != "assistant":
            continue
        meta = row.metadata_json or {}
        if row.msg_id == assistant_msg_id or meta.get("ui_msg_id") == assistant_msg_id:
            target_idx = i
            break

    if target_idx is None:
        return None

    user_row = None
    for j in range(target_idx - 1, -1, -1):
        if rows[j].role == "user":
            user_row = rows[j]
            break

    db.delete(rows[target_idx])
    if user_row:
        db.delete(user_row)

    _touch_conversation(conv)
    db.add(conv)
    db.commit()
    return conversation_detail(db, user_id, conv_id, message_limit=8)


def persist_chat_turn(
    db: Session,
    user_id: str,
    conv_id: str,
    *,
    user_msg_id: str,
    assistant_msg_id: str,
    user_content: str,
    assistant_content: str,
    user_metadata: dict | None = None,
    assistant_metadata: dict | None = None,
    bind_paper_id: str | None = None,
) -> None:
    conv = get_conversation(db, user_id, conv_id)
    if not conv:
        raise ValueError("会话不存在或无权访问")

    _upsert_message(
        db,
        msg_id=user_msg_id,
        conv_id=conv_id,
        role="user",
        content=user_content,
        metadata=user_metadata,
    )
    _upsert_message(
        db,
        msg_id=assistant_msg_id,
        conv_id=conv_id,
        role="assistant",
        content=assistant_content,
        metadata=assistant_metadata,
    )

    if bind_paper_id:
        conv.bind_paper_id = bind_paper_id
    conv.model_name = startup.config.model_name if startup.config else conv.model_name
    _touch_conversation(conv)
    db.add(conv)
    db.commit()
