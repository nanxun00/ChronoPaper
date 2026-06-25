"""对话原生 Tool 服务（日期、天气等，默认启用）。"""
from __future__ import annotations

import json

from src.integrations.native_tools.datetime_tool import get_current_datetime
from src.integrations.native_tools.weather_tool import get_weather
from src.utils.logging_config import setup_logger

logger = setup_logger("native-tools")

NATIVE_TOOL_NAMES = frozenset({"get_current_datetime", "get_weather"})

_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_datetime",
            "description": "获取服务器当前日期与时间。用户询问今天几号、现在几点、星期几时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": "IANA 时区，默认 Asia/Shanghai",
                        "default": "Asia/Shanghai",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询指定城市当前天气（温度、湿度、风力、天气状况）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，如 太原、北京、Shanghai",
                    },
                },
                "required": ["city"],
            },
        },
    },
]


class NativeToolService:
    def get_tools_schema(self) -> list[dict]:
        return list(_TOOL_SCHEMAS)

    def call_tool(self, tool_name: str, arguments: dict) -> dict:
        args = dict(arguments or {})
        try:
            if tool_name == "get_current_datetime":
                result = get_current_datetime(timezone=args.get("timezone") or "Asia/Shanghai")
            elif tool_name == "get_weather":
                result = get_weather(city=args.get("city") or "")
            else:
                return {"ok": False, "error": f"未知原生工具: {tool_name}"}
        except Exception as exc:
            logger.exception("native tool failed: %s", tool_name)
            return {"ok": False, "error": f"工具执行异常: {exc}"}

        if not result.get("ok"):
            return {"ok": False, "error": result.get("error") or "查询失败"}
        return {"ok": True, "content": json.dumps(result, ensure_ascii=False, indent=2)}


_native_tool_service: NativeToolService | None = None


def get_native_tool_service() -> NativeToolService:
    global _native_tool_service
    if _native_tool_service is None:
        _native_tool_service = NativeToolService()
    return _native_tool_service
