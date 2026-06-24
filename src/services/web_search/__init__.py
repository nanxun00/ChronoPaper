"""WebSearch 联网搜索服务层。"""
from __future__ import annotations

from dataclasses import dataclass
from src.integrations.web_search import WebSearchMCPClient
from src.utils.logging_config import setup_logger

logger = setup_logger("web-search-service")


@dataclass
class WebSearchServiceConfig:
    enabled: bool = False
    url: str = ""
    auth_token: str = ""


class WebSearchService:
    def __init__(self, config: WebSearchServiceConfig):
        self.config = config
        self._client: WebSearchMCPClient | None = None

    @property
    def is_enabled(self) -> bool:
        return self.config.enabled and bool(self.config.url)

    def _ensure_client(self) -> WebSearchMCPClient | None:
        if not self.is_enabled:
            return None
        if self._client is None:
            logger.info(f"正在连接 WebSearch MCP: {self.config.url}")
            self._client = WebSearchMCPClient(
                url=self.config.url,
                auth_token=self.config.auth_token,
            )
            tools = self._client.connect()
            if not tools:
                logger.error(f"WebSearch MCP 连接失败或未发现工具。请检查 URL 是否为真实的 Endpoint: {self.config.url}")
                return None
            logger.info(f"WebSearch MCP 连接成功，发现工具: {[t.get('name') for t in tools]}")
        return self._client

    def get_tools_schema(self, enable_web_search: bool) -> list[dict]:
        if not enable_web_search or not self.is_enabled:
            return []
        client = self._ensure_client()
        if not client:
            return []
        return client.get_tools_schema()

    def call_tool(self, tool_name: str, arguments: dict) -> dict:
        client = self._ensure_client()
        if not client:
            return {"ok": False, "error": "WebSearch 客户端未初始化"}
        result = client.call_tool(tool_name, arguments)
        return {"ok": result.ok, "content": result.content, "error": result.error}


_web_search_service: WebSearchService | None = None


def get_web_search_service() -> WebSearchService:
    global _web_search_service
    if _web_search_service is None:
        from src.settings import get_settings
        s = get_settings()
        # 这里需要从 settings 获取配置，稍后我们在 settings.py 中添加这些字段
        _web_search_service = WebSearchService(WebSearchServiceConfig(
            enabled=getattr(s, "web_search_enabled", True),
            url=getattr(s, "web_search_url", "https://modelscope.cn/mcp/servers/slcatwujian/bing-cn-mcp-server"),
            auth_token=getattr(s, "web_search_auth_token", getattr(s, "memos_auth_token", "")),
        ))
    return _web_search_service
