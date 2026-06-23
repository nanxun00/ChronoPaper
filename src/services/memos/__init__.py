"""MemOS 记忆服务层。

封装 MemOS MCP 客户端，提供：
- 会话级短期工作记忆（自动管理，会话结束清空）
- 用户级长期持久记忆（跨会话保留，权重分级）
- 独立开关控制（enable_memory 布尔参数）
- user_id + session_id 双维度隔离
- 调用日志记录
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import json

from src.integrations.memos import MemosMCPClient, MemosCallLog
from src.utils.logging_config import setup_logger

logger = setup_logger("memos-service")


@dataclass
class MemoryServiceConfig:
    """记忆服务配置。"""
    enabled: bool = False
    url: str = ""
    auth_token: str = ""


class MemoryService:
    """MemOS 记忆服务。

    所有记忆数据采用 user_id + session_id 双维度隔离，
    云端存储以双字段作为联合过滤条件。
    """

    def __init__(self, config: MemoryServiceConfig):
        self.config = config
        self._client: MemosMCPClient | None = None
        self._call_logs: list[MemosCallLog] = []

    @property
    def is_enabled(self) -> bool:
        return self.config.enabled and bool(self.config.url)

    def _ensure_client(self) -> MemosMCPClient | None:
        """懒加载 MCP 客户端。"""
        if not self.is_enabled:
            return None
        if self._client is None:
            self._client = MemosMCPClient(
                url=self.config.url,
                auth_token=self.config.auth_token,
            )
            tools = self._client.connect()
            if not tools:
                last_error = getattr(self._client, "_last_error", "")
                logger.warning(
                    "MemOS MCP client connected but no tools available: %s",
                    last_error or "unknown error",
                )
                return None
        return self._client

    def _client_error(self, with_memories: bool = False) -> dict:
        last_error = ""
        if self._client is not None:
            last_error = getattr(self._client, "_last_error", "")
        msg = last_error or "MemOS 客户端未初始化，请检查 .env 中 MEMOS_URL / MEMOS_AUTH_TOKEN"
        result: dict = {"ok": False, "error": msg}
        if with_memories:
            result["memories"] = []
        return result

    # ── 工具 Schema ─────────────────────────────────────────────────

    def get_tools_schema(self, enable_memory: bool) -> list[dict]:
        """获取记忆工具 Schema。

        开关关闭时返回空列表，实现硬隔离：
        业务工具管理器不加载 MemOS 全套 MCP 工具，
        传递给大模型的 tools 数组不含记忆相关函数，
        所有模型完全感知不到记忆读写、检索能力。
        """
        if not enable_memory or not self.is_enabled:
            return []
        client = self._ensure_client()
        if not client:
            return []
        return client.get_tools_schema()

    # ── 记忆操作 ────────────────────────────────────────────────────

    def add_memory(
        self,
        user_id: str,
        session_id: str,
        content: str,
        enable_memory: bool = True,
    ) -> dict:
        """提取对话关键信息，写入当前会话长期记忆库。

        Args:
            user_id: 用户 ID（强制参数）
            session_id: 会话 ID（强制参数）
            content: 要存储的对话内容
            enable_memory: 记忆开关（每条对话请求独立控制）

        Returns:
            {"ok": bool, "content": str, "error": str}
        """
        if not enable_memory or not self.is_enabled:
            return {"ok": False, "error": "记忆功能未启用"}

        if not user_id or not session_id:
            return {"ok": False, "error": "缺少 user_id 或 session_id 参数"}

        client = self._ensure_client()
        if not client:
            return self._client_error()

        result = client.add_memory(user_id, session_id, content)
        self._log_call(MemosCallLog(
            user_id=user_id,
            session_id=session_id,
            enabled=enable_memory,
            tool_name="add_memory",
            arguments={"content_length": len(content)},
            result_content=result.content[:200],
            ok=result.ok,
            latency_ms=result.latency_ms,
        ))
        return {"ok": result.ok, "content": result.content, "error": result.error}

    def search_memory(
        self,
        user_id: str,
        session_id: str,
        query: str,
        top_k: int = 5,
        enable_memory: bool = True,
    ) -> dict:
        """基于用户当前提问做语义向量检索，召回同会话历史相关记忆片段。

        记忆检索仅返回同一用户、同一会话下的历史记忆，
        自动过滤其他用户、其他对话窗口的记忆内容。
        """
        if not enable_memory or not self.is_enabled:
            return {"ok": False, "error": "记忆功能未启用", "memories": []}

        if not user_id or not session_id:
            return {"ok": False, "error": "缺少 user_id 或 session_id 参数", "memories": []}

        client = self._ensure_client()
        if not client:
            return self._client_error(with_memories=True)

        result = client.search_memory(user_id, session_id, query, top_k)
        self._log_call(MemosCallLog(
            user_id=user_id,
            session_id=session_id,
            enabled=enable_memory,
            tool_name="search_memory",
            arguments={"query_length": len(query), "top_k": top_k},
            result_content=result.content[:500],
            ok=result.ok,
            latency_ms=result.latency_ms,
        ))
        return {
            "ok": result.ok,
            "content": result.content,
            "error": result.error,
            "memories": result.content if result.ok else [],
        }

    def clear_session_memory(
        self,
        user_id: str,
        session_id: str,
        enable_memory: bool = True,
    ) -> dict:
        """清空当前会话全部短期、长期记忆数据。

        配套会话操作工具：支持一键清空当前 session 下全部记忆，
        新建对话自动生成全新 session_id 实现记忆隔离。
        """
        if not enable_memory or not self.is_enabled:
            return {"ok": False, "error": "记忆功能未启用"}

        if not user_id or not session_id:
            return {"ok": False, "error": "缺少 user_id 或 session_id 参数"}

        client = self._ensure_client()
        if not client:
            return self._client_error()

        result = client.clear_session_memory(user_id, session_id)
        self._log_call(MemosCallLog(
            user_id=user_id,
            session_id=session_id,
            enabled=enable_memory,
            tool_name="clear_session_memory",
            arguments={},
            result_content=result.content[:200],
            ok=result.ok,
            latency_ms=result.latency_ms,
        ))
        return {"ok": result.ok, "content": result.content, "error": result.error}

    def list_all_memories(
        self,
        user_id: str,
        session_id: str = "",
        top_k: int = 100,
        enable_memory: bool = True,
    ) -> dict:
        """获取用户的所有长期记忆（全局，不按会话分割）。

        session_id 为空时进行全局检索，返回该用户所有会话的记忆。
        """
        if not enable_memory or not self.is_enabled:
            return {"ok": False, "error": "记忆功能未启用", "memories": []}

        if not user_id:
            return {"ok": False, "error": "缺少 user_id 参数", "memories": []}

        client = self._ensure_client()
        if not client:
            return self._client_error(with_memories=True)

        result = client.list_all_memories(user_id, session_id, top_k)
        self._log_call(MemosCallLog(
            user_id=user_id,
            session_id=session_id or "global",
            enabled=enable_memory,
            tool_name="list_all_memories",
            arguments={"top_k": top_k, "global": not session_id},
            result_content=result.content[:2000],
            ok=result.ok,
            latency_ms=result.latency_ms,
        ))
        return {
            "ok": result.ok,
            "content": result.content,
            "error": result.error,
            "memories": self.format_memory_display_items(result.content) if result.ok else [],
        }

    @staticmethod
    def _format_memos_list_entry(entry: dict, list_key: str) -> str | None:
        """将单条 MemOS 记忆转为可读文本；跳过未提炼的原始对话消息。"""
        if "role" in entry and "content" in entry:
            if not any(entry.get(k) for k in ("memory_key", "memory_value", "preference", "memory")):
                return None

        if list_key == "memory_detail_list":
            key = str(entry.get("memory_key") or entry.get("key") or "").strip()
            value = str(
                entry.get("memory_value")
                or entry.get("value")
                or entry.get("summary")
                or entry.get("memory")
                or ""
            ).strip()
            if not value:
                return None
            prefix = f"【事实记忆】{key}：" if key else "【事实记忆】"
            return f"{prefix}{value}"

        if list_key == "preference_detail_list":
            pref = str(entry.get("preference") or "").strip()
            if not pref:
                return None
            reasoning = str(entry.get("reasoning") or "").strip()
            if reasoning:
                return f"【偏好记忆】{pref}\n（依据：{reasoning}）"
            return f"【偏好记忆】{pref}"

        if list_key == "tool_memory_detail_list":
            text = str(
                entry.get("summary")
                or entry.get("memory_value")
                or entry.get("content")
                or entry.get("trajectory")
                or ""
            ).strip()
            if not text:
                return None
            tool = str(entry.get("tool_name") or entry.get("name") or "").strip()
            prefix = f"【工具记忆】{tool}：" if tool else "【工具记忆】"
            return f"{prefix}{text}"

        if list_key == "skill_detail_list":
            name = str(entry.get("skill_name") or entry.get("name") or "").strip()
            desc = str(
                entry.get("description")
                or entry.get("summary")
                or entry.get("memory_value")
                or entry.get("content")
                or ""
            ).strip()
            if not name and not desc:
                return None
            if name and desc:
                return f"【技能记忆】{name}：{desc}"
            return f"【技能记忆】{name or desc}"

        return None

    @staticmethod
    def format_memory_display_items(content: str) -> list[str]:
        """将 MemOS MCP 返回内容转为设置页可展示的提炼记忆列表。"""
        if not content:
            return []
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            return [line for line in content.split("\n") if line.strip()]

        # list_all_memories 返回的是 JSON 数组
        if isinstance(payload, list):
            return [str(item) for item in payload if str(item).strip()]

        if not isinstance(payload, dict):
            return [str(payload)]

        data = payload.get("data")
        if isinstance(data, dict):
            items: list[str] = []
            for key in (
                "memory_detail_list",
                "preference_detail_list",
                "tool_memory_detail_list",
                "skill_detail_list",
            ):
                for entry in data.get(key) or []:
                    if isinstance(entry, dict):
                        text = MemoryService._format_memos_list_entry(entry, key)
                        if text:
                            items.append(text)
                    elif entry:
                        items.append(str(entry))
            note = data.get("preference_note")
            if note and str(note).strip():
                items.append(f"【偏好备注】{str(note).strip()}")
            return items

        if isinstance(data, list):
            return [str(item) for item in data]

        return []

    # ── 日志与统计 ──────────────────────────────────────────────────

    def _log_call(self, log: MemosCallLog) -> None:
        """记录 MemOS MCP 调用日志。"""
        self._call_logs.append(log)
        logger.info(
            "MemOS call: user=%s session=%s tool=%s ok=%s latency=%.0fms",
            log.user_id[:8],
            log.session_id[:8],
            log.tool_name,
            log.ok,
            log.latency_ms,
        )

    def get_call_stats(self) -> dict:
        """获取记忆调用统计，用于消融实验对比、云端托管服务费用核算。"""
        total = len(self._call_logs)
        success = sum(1 for log in self._call_logs if log.ok)
        failed = total - success
        avg_latency = (
            sum(log.latency_ms for log in self._call_logs) / total
            if total > 0 else 0
        )
        return {
            "total_calls": total,
            "success": success,
            "failed": failed,
            "avg_latency_ms": round(avg_latency, 2),
            "logs": [
                {
                    "user_id": log.user_id,
                    "session_id": log.session_id,
                    "enabled": log.enabled,
                    "tool_name": log.tool_name,
                    "ok": log.ok,
                    "latency_ms": round(log.latency_ms, 2),
                    "timestamp": log.timestamp,
                }
                for log in self._call_logs[-100:]  # 最近 100 条
            ],
        }

    def clear_logs(self) -> None:
        """清空调用日志。"""
        self._call_logs.clear()


# ── 全局单例 ────────────────────────────────────────────────────────

_memory_service: MemoryService | None = None


def get_memory_service() -> MemoryService:
    """获取全局记忆服务实例。"""
    global _memory_service
    if _memory_service is None:
        from src.integrations.memos import _normalize_auth_token
        from src.settings import get_settings
        s = get_settings()
        _memory_service = MemoryService(MemoryServiceConfig(
            enabled=s.memos_enabled,
            url=s.memos_url,
            auth_token=_normalize_auth_token(s.memos_auth_token),
        ))
    return _memory_service


def reset_memory_service() -> None:
    """重置记忆服务（用于测试或配置变更）。"""
    global _memory_service
    _memory_service = None
