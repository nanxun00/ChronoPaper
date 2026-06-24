"""聊天会话与消息 ORM。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.dialects.mysql import LONGTEXT

from src.models.base import Base

_CHAT_TABLE_ARGS = {
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


class ChatConversation(Base):
    __tablename__ = "chat_conversation"
    __table_args__ = _CHAT_TABLE_ARGS

    conv_id = Column(String(64), primary_key=True)
    user_id = Column(String(255), nullable=False, index=True)
    title = Column(String(255), nullable=False, default="新对话")
    bind_paper_id = Column(String(128), nullable=True)
    bind_doc_id = Column(String(64), nullable=True)
    model_name = Column(String(64), nullable=False, default="")
    system_prompt = Column(LONGTEXT, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_active_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "conv_id": self.conv_id,
            "user_id": self.user_id,
            "title": self.title,
            "bind_paper_id": self.bind_paper_id,
            "bind_doc_id": self.bind_doc_id,
            "model_name": self.model_name,
            "system_prompt": self.system_prompt,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "last_active_at": self.last_active_at.strftime("%Y-%m-%d %H:%M:%S") if self.last_active_at else None,
        }


class ChatMessage(Base):
    __tablename__ = "chat_message"
    __table_args__ = _CHAT_TABLE_ARGS

    msg_id = Column(String(64), primary_key=True)
    conv_id = Column(
        String(64),
        ForeignKey("chat_conversation.conv_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(16), nullable=False)
    content = Column(LONGTEXT, nullable=False, default="")
    total_tokens = Column(Integer, nullable=False, default=0)
    metadata_json = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "msg_id": self.msg_id,
            "conv_id": self.conv_id,
            "role": self.role,
            "content": self.content,
            "total_tokens": self.total_tokens,
            "metadata": self.metadata_json or {},
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }
