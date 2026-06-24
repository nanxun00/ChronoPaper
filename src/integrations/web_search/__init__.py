"""WebSearch 云端 Hosted MCP 搜索服务客户端。

通过 SSE/Streamable HTTP 协议调用 ModelScope MCP 广场托管的 Bing Search 服务。
提供联网搜索与网页抓取功能。
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import requests

from src.utils.logging_config import setup_logger

logger = setup_logger("web-search-client")


def _normalize_auth_token(token: str) -> str:
    """去掉首尾空白，并移除用户误填的 Bearer 前缀。"""
    token = (token or "").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token


def _format_request_error(exc: Exception) -> str:
    """将 requests 异常转为前端可读的提示。"""
    response = getattr(exc, "response", None)
    if response is not None and response.status_code == 401:
        return (
            "ModelScope MCP 认证失败（401）。请检查有效的 "
            "WEB_SEARCH_AUTH_TOKEN。"
        )
    return str(exc)


@dataclass
class WebSearchToolResult:
    """MCP 工具调用结果。"""
    tool_name: str
    ok: bool
    content: str = ""
    error: str = ""
    latency_ms: float = 0.0


class WebSearchMCPClient:
    """WebSearch 云端 Hosted MCP 客户端。"""

    def __init__(self, url: str, auth_token: str = ""):
        self.url = url.rstrip("/")
        self.auth_token = _normalize_auth_token(auth_token)
        self._mcp_session_id: str | None = None
        self._tools: list[dict] = []
        self._last_error: str = ""

    def connect(self) -> list[dict]:
        """初始化 MCP 连接，获取可用工具列表。"""
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
                logger.info("WebSearch MCP session established: %s", mcp_session_id[:20])

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
            logger.info("WebSearch MCP connected, tools: %s", [t["name"] for t in self._tools])
            return self._tools
        except Exception as exc:
            logger.warning("WebSearch MCP connect failed: %s", exc)
            self._last_error = _format_request_error(exc)
            return []

    def call_tool(self, tool_name: str, arguments: dict) -> WebSearchToolResult:
        """调用 WebSearch MCP 工具。"""
        start = time.time()
        try:
            if not self._mcp_session_id and not self._tools:
                self.connect()
            if not self._mcp_session_id:
                return WebSearchToolResult(
                    tool_name=tool_name,
                    ok=False,
                    error="WebSearch MCP 未连接",
                    latency_ms=(time.time() - start) * 1000,
                )
            
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
                headers=self._headers(),
                json=payload,
                timeout=30,
            )
            
            if resp.status_code == 401:
                self._mcp_session_id = None
                self._tools = []
                self.connect()
                if self._mcp_session_id:
                    resp = requests.post(self.url, headers=self._headers(), json=payload, timeout=30)
            
            resp.raise_for_status()
            result = resp.json()
            content = self._extract_content(result)
            is_error = bool(result.get("result", {}).get("isError"))
            return WebSearchToolResult(
                tool_name=tool_name,
                ok=not is_error,
                content=content,
                error=content if is_error else "",
                latency_ms=(time.time() - start) * 1000,
            )
        except Exception as exc:
            return WebSearchToolResult(
                tool_name=tool_name,
                ok=False,
                error=_format_request_error(exc),
                latency_ms=(time.time() - start) * 1000,
            )

    def get_tools_schema(self) -> list[dict]:
        if not self._tools:
            self.connect()
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

    def _headers(self) -> dict:
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
        content_list = result.get("result", {}).get("content", [])
        parts = []
        for item in content_list:
            if item.get("type") == "text":
                parts.append(item.get("text", ""))
            else:
                parts.append(json.dumps(item, ensure_ascii=False))
        return "\n".join(parts) if parts else json.dumps(result, ensure_ascii=False)
