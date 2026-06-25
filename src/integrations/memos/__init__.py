"""MemOS 云端 Hosted MCP 记忆服务客户端。

通过 SSE/Streamable HTTP 协议调用 ModelScope MCP 广场托管的 MemOS 服务，
提供 add_memory / search_memory / clear_session_memory 三类工具。
所有记忆数据采用 user_id + session_id 双维度隔离。
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import requests

from src.utils.logging_config import setup_logger

logger = setup_logger("memos-client")


def _normalize_auth_token(token: str) -> str:
    """去掉首尾空白，并移除用户误填的 Bearer 前缀。"""
    token = (token or "").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token


def _format_request_error(exc: Exception) -> str:
    """将 requests 异常转为前端可读的提示。"""
    response = getattr(exc, "response", None)
    if response is not None:
        status = response.status_code
        body = (response.text or "")[:500]
        if status == 401:
            return (
                "ModelScope MCP 认证失败（401）。请在项目根目录 .env 中配置有效的 "
                "MEMOS_AUTH_TOKEN，"
                "保存后点击「重启服务」并再次刷新记忆。若暂不使用长期记忆，可将 MEMOS_ENABLED 设为 false。"
            )
        if status == 410 or "Url is expired" in body or "url is expired" in body.lower():
            return (
                "MemOS地址已过期（410）。请重新部署/刷新 MemOS 服务，"
                "将新的 MEMOS_URL 写入 .env 后重启后端。Hosted MCP 链接有时效，过期后必须更换。"
            )
    return str(exc)


def _is_url_expired_error(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    if response is None:
        return False
    if response.status_code == 410:
        return True
    body = (response.text or "").lower()
    return "url is expired" in body


@dataclass
class MemosToolResult:
    """MCP 工具调用结果。"""
    tool_name: str
    ok: bool
    content: str = ""
    error: str = ""
    latency_ms: float = 0.0


@dataclass
class MemosCallLog:
    """MCP 调用日志记录。"""
    user_id: str
    session_id: str
    enabled: bool
    tool_name: str
    arguments: dict = field(default_factory=dict)
    result_content: str = ""
    ok: bool = True
    latency_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)


class MemosMCPClient:
    """MemOS 云端 Hosted MCP 客户端。

    使用 streamable_http 协议与云端 MemOS 服务通信，
    无需本地部署 Docker / Milvus / Neo4j / MySQL / Redis。
    """

    def __init__(self, url: str, auth_token: str = ""):
        self.url = url.rstrip("/")
        self.auth_token = _normalize_auth_token(auth_token)
        self._session_id: str | None = None
        self._mcp_session_id: str | None = None
        self._tools: list[dict] = []
        self._last_error: str = ""
        self._url_expired: bool = False

    @property
    def url_expired(self) -> bool:
        return self._url_expired

    def _mark_disconnected(self, exc: Exception | None = None) -> None:
        self._mcp_session_id = None
        self._tools = []
        if exc is not None:
            self._last_error = _format_request_error(exc)
            if _is_url_expired_error(exc):
                self._url_expired = True

    # ── 连接与会话管理 ──────────────────────────────────────────────

    def connect(self) -> list[dict]:
        """初始化 MCP 连接，获取可用工具列表。"""
        if self._url_expired:
            return []
        try:
            headers = self._headers()
            init_payload = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "ChronoPaper", "version": "1.0.0"},
                },
            }
            resp = requests.post(
                self.url,
                headers=headers,
                json=init_payload,
                timeout=15,
            )
            resp.raise_for_status()

            mcp_session_id = resp.headers.get("Mcp-Session-Id", "")
            if mcp_session_id:
                self._mcp_session_id = mcp_session_id
                logger.info("MemOS MCP session established: %s", mcp_session_id[:20])

            notif = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            }
            requests.post(self.url, headers=self._headers(), json=notif, timeout=10)

            tools_resp = requests.post(
                self.url,
                headers=self._headers(),
                json={
                    "jsonrpc": "2.0",
                    "id": str(uuid.uuid4()),
                    "method": "tools/list",
                    "params": {},
                },
                timeout=15,
            )
            tools_resp.raise_for_status()
            result = tools_resp.json()
            self._tools = result.get("result", {}).get("tools", [])
            self._last_error = ""
            logger.info("MemOS MCP connected, tools: %s", [t["name"] for t in self._tools])
            return self._tools
        except Exception as exc:
            logger.warning("MemOS MCP connect failed: %s", exc)
            if hasattr(exc, "response") and exc.response is not None:
                logger.warning(
                    "MemOS MCP error response: %s %s",
                    exc.response.status_code,
                    exc.response.text[:500],
                )
            self._mark_disconnected(exc)
            return []

    def new_session(self) -> str:
        """创建新的会话 ID。"""
        self._session_id = str(uuid.uuid4())
        return self._session_id

    @property
    def session_id(self) -> str | None:
        return self._session_id

    # ── MCP 工具调用 ────────────────────────────────────────────────

    def call_tool(self, tool_name: str, arguments: dict) -> MemosToolResult:
        """调用 MemOS MCP 工具。401 时自动重连；410 时标记 URL 过期并停止重试。"""
        start = time.time()
        if self._url_expired:
            return MemosToolResult(
                tool_name=tool_name,
                ok=False,
                error=self._last_error or "MemOS MCP 地址已过期，请更新 MEMOS_URL",
                latency_ms=0,
            )
        try:
            if not self._mcp_session_id and not self._tools:
                self.connect()
            if not self._mcp_session_id:
                return MemosToolResult(
                    tool_name=tool_name,
                    ok=False,
                    error=self._last_error or "MemOS MCP 未连接，请检查 MEMOS_URL 与网络",
                    latency_ms=(time.time() - start) * 1000,
                )
            headers = self._headers()
            payload = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments,
                },
            }
            resp = requests.post(
                self.url,
                headers=headers,
                json=payload,
                timeout=30,
            )
            if resp.status_code == 401:
                logger.info("MemOS MCP session expired (401), reconnecting...")
                self._mark_disconnected()
                self.connect()
                if self._mcp_session_id:
                    headers = self._headers()
                    resp = requests.post(
                        self.url,
                        headers=headers,
                        json=payload,
                        timeout=30,
                    )
            if resp.status_code == 410:
                err = requests.HTTPError(response=resp)
                self._mark_disconnected(err)
                return MemosToolResult(
                    tool_name=tool_name,
                    ok=False,
                    error=self._last_error,
                    latency_ms=(time.time() - start) * 1000,
                )
            resp.raise_for_status()
            result = resp.json()
            content = self._extract_content(result)
            is_error = bool(result.get("result", {}).get("isError"))
            latency = (time.time() - start) * 1000
            return MemosToolResult(
                tool_name=tool_name,
                ok=not is_error,
                content=content,
                error=content if is_error else "",
                latency_ms=latency,
            )
        except Exception as exc:
            latency = (time.time() - start) * 1000
            logger.warning("MemOS call_tool %s failed: %s", tool_name, exc)
            self._mark_disconnected(exc)
            return MemosToolResult(
                tool_name=tool_name,
                ok=False,
                error=self._last_error,
                latency_ms=latency,
            )

    # ── 高层记忆操作（适配 MemOS 实际 API） ─────────────────────────

    def add_memory(
        self,
        user_id: str,
        session_id: str,
        content: str,
    ) -> MemosToolResult:
        """提取对话关键信息，写入当前会话长期记忆库。

        MemOS 实际工具为 add_message，使用 conversation_first_message 作为会话标识。
        """
        return self.call_tool("add_message", {
            "conversation_first_message": session_id,
            "messages": [{"role": "user", "content": content}],
        })

    def search_memory(
        self,
        user_id: str,
        session_id: str,
        query: str,
        top_k: int = 5,
    ) -> MemosToolResult:
        """基于用户当前提问做语义向量检索，召回相关记忆片段。

        MemOS MCP 要求 query 与 conversation_first_message 同时提供（均为必填）。
        """
        arguments: dict = {
            "query": query or " ",
            "conversation_first_message": session_id or "default",
        }
        return self.call_tool("search_memory", arguments)

    def clear_session_memory(
        self,
        user_id: str,
        session_id: str,
    ) -> MemosToolResult:
        """清空当前会话全部记忆数据。

        先搜索该会话所有记忆，再逐一删除。
        """
        # 先搜索该会话所有记忆
        search_result = self.search_memory(user_id, session_id, query="", top_k=100)
        if not search_result.ok:
            return search_result

        # 解析返回的记忆 ID 并逐一删除
        memory_ids = self._parse_memory_ids(search_result.content)
        if not memory_ids:
            return MemosToolResult(
                tool_name="clear_session_memory",
                ok=True,
                content="当前会话无记忆数据",
            )

        results = []
        for mid in memory_ids:
            r = self.call_tool("delete_memory", {"memory_ids": [mid]})
            results.append(f"删除 {mid}: {'成功' if r.ok else r.error}")

        return MemosToolResult(
            tool_name="clear_session_memory",
            ok=True,
            content="; ".join(results),
        )

    def list_all_memories(
        self,
        user_id: str,
        session_id: str = "",
        top_k: int = 100,
    ) -> MemosToolResult:
        """获取所有长期记忆（全局或按会话过滤）。

        使用 search_memory 检索对话记忆，需要 conversation_first_message 参数。
        全局查询时尝试多个常见会话标识。
        """
        # 先尝试 get_user_profile 获取偏好
        profile_result = self.call_tool(
            "get_user_profile",
            {
                "include_preference": True,
                "include_tool_memory": True,
            },
        )

        if not profile_result.ok:
            err = profile_result.error or ""
            if "401" in err or "Unauthorized" in err:
                return MemosToolResult(
                    tool_name="list_all_memories",
                    ok=False,
                    error=(
                        f"MemOS 认证失败（401）：{err}。"
                        "请检查 .env 中 MEMOS_AUTH_TOKEN 是否有效。"
                    ),
                )
            if self._url_expired or "410" in err or "过期" in err:
                return MemosToolResult(
                    tool_name="list_all_memories",
                    ok=False,
                    error=err or self._last_error,
                )
            if not self._mcp_session_id:
                return MemosToolResult(
                    tool_name="list_all_memories",
                    ok=False,
                    error=err or self._last_error or "MemOS MCP 未连接",
                )

        # 解析偏好数据
        preferences = []
        if profile_result.ok and profile_result.content:
            try:
                profile_data = json.loads(profile_result.content)
                pref_list = profile_data.get("data", {}).get("preference_detail_list", [])
                for pref in pref_list:
                    content = pref.get("content", "") or pref.get("preference", "")
                    if content:
                        preferences.append(f"[偏好] {content}")
            except (json.JSONDecodeError, KeyError):
                pass

        # 尝试用常见会话标识检索对话记忆
        all_memories = list(preferences)
        test_sessions = [session_id, "default", "global", ""] if session_id else ["default", "global", ""]

        for test_sid in test_sessions:
            if not test_sid:
                continue
            search_result = self.search_memory(user_id, test_sid, query="记忆 偏好 喜欢", top_k=top_k)
            if search_result.ok and search_result.content:
                try:
                    search_data = json.loads(search_result.content)
                    mem_list = search_data.get("data", {}).get("memory_detail_list", [])
                    for mem in mem_list:
                        content = mem.get("content", "") or mem.get("text", "")
                        if content and content not in all_memories:
                            all_memories.append(content)
                except (json.JSONDecodeError, KeyError):
                    if search_result.content not in all_memories:
                        all_memories.append(search_result.content)

        if all_memories:
            return MemosToolResult(
                tool_name="list_all_memories",
                ok=True,
                content=json.dumps(all_memories, ensure_ascii=False),
            )
        else:
            return MemosToolResult(
                tool_name="list_all_memories",
                ok=True,
                content="暂无记忆数据",
            )

    # ── 工具 Schema（供 Function Calling 注入） ─────────────────────

    def get_tools_schema(self) -> list[dict]:
        """返回 MemOS 工具的 OpenAI Function Calling Schema。"""
        if self._url_expired:
            return []
        if not self._tools:
            self.connect()
        if not self._tools:
            return []
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("inputSchema", {}),
                },
            }
            for t in self._tools
        ]

    # ─ 内部方法 ────────────────────────────────────────────────────

    def _headers(self) -> dict:
        # ModelScope Hosted MCP 要求同时接受 json 与 event-stream
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        if self._mcp_session_id:
            headers["Mcp-Session-Id"] = self._mcp_session_id
        return headers

    @staticmethod
    def _extract_content(result: dict) -> str:
        """从 MCP tools/call 响应中提取文本内容。"""
        content_list = result.get("result", {}).get("content", [])
        parts = []
        for item in content_list:
            if item.get("type") == "text":
                parts.append(item.get("text", ""))
            else:
                parts.append(json.dumps(item, ensure_ascii=False))
        return "\n".join(parts) if parts else json.dumps(result, ensure_ascii=False)

    @staticmethod
    def _parse_memory_ids(content: str) -> list[str]:
        """从 search_memory 返回内容中解析记忆 ID 列表。"""
        import re
        ids = []
        # 尝试匹配 "memory_id": "xxx" 或 "id": "xxx" 格式
        patterns = [
            r'"memory_id"\s*:\s*"([^"]+)"',
            r'"id"\s*:\s*"([^"]+)"',
            r'"memoryId"\s*:\s*"([^"]+)"',
        ]
        for pattern in patterns:
            ids.extend(re.findall(pattern, content))
        return list(set(ids))
