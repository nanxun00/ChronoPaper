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


def build_llm_history(db: Session, conv_id: str) -> list[dict]:
    """构建发给大模型的 history（user/assistant 纯文本）。"""
    rows = list_messages(db, conv_id)
    history: list[dict] = []
    for row in rows:
        if row.role not in ("user", "assistant"):
            continue
        history.append({"role": row.role, "content": row.content or ""})
    return history


def _ui_message_from_row(row: ChatMessage) -> dict:
    meta = row.metadata_json or {}
    if row.role == "user":
        return {
            "id": meta.get("ui_msg_id") or row.msg_id,
            "role": "sent",
            "text": row.content,
            "images": meta.get("images") or [],
            "citations": meta.get("citations") or [],
            "status": "finished",
        }
    return {
        "id": meta.get("ui_msg_id") or row.msg_id,
        "role": "received",
        "text": row.content,
        "ponder": meta.get("reasoning_content") or "",
        "refs": meta.get("refs"),
        "model_name": meta.get("model_name"),
        "status": meta.get("status") or "finished",
        "meta": meta.get("chat_meta") or {},
    }


def conversation_detail(db: Session, user_id: str, conv_id: str) -> dict | None:
    conv = get_conversation(db, user_id, conv_id)
    if not conv:
        return None
    rows = list_messages(db, conv_id)
    messages = [_ui_message_from_row(row) for row in rows if row.role in ("user", "assistant")]
    return {
        **conv.to_dict(),
        "messages": messages,
        "history": build_llm_history(db, conv_id),
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
    return conversation_detail(db, user_id, conv_id)


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
