"""解析 LLM 输出的工具调用（MiMo XML / 简易 JSON）。"""
from __future__ import annotations

import json
import re

from src.services.skills.agent.tools import ToolCall

_MIMO_BLOCK_RE = re.compile(
    r"<function=(\w+)>(.*?)</function>",
    re.DOTALL | re.IGNORECASE,
)
_MIMO_PARAM_RE = re.compile(
    r"<parameter=(\w+)>(.*?)</parameter>",
    re.DOTALL | re.IGNORECASE,
)
_JSON_TOOL_RE = re.compile(r"\{[\s\S]*\"name\"[\s\S]*\}")


def parse_tool_calls(text: str) -> list[ToolCall]:
    raw = text or ""
    calls: list[ToolCall] = []
    for match in _MIMO_BLOCK_RE.finditer(raw):
        name = match.group(1).strip().lower()
        body = match.group(2)
        args: dict[str, str] = {}
        for pm in _MIMO_PARAM_RE.finditer(body):
            args[pm.group(1).strip()] = pm.group(2).strip()
        if name:
            calls.append(ToolCall(name=name, arguments=args))

    if calls:
        return calls

    # OpenAI-style tool_calls on message object handled in runner
    for jmatch in _JSON_TOOL_RE.finditer(raw):
        snippet = jmatch.group(0)
        try:
            data = json.loads(snippet)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("name"):
            args = data.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {"file_path": args}
            if isinstance(args, dict):
                calls.append(
                    ToolCall(
                        name=str(data["name"]).lower(),
                        arguments={str(k): str(v) for k, v in args.items()},
                    )
                )
    return calls


def strip_tool_calls(text: str) -> str:
    """去掉工具调用块，保留面向用户的文字。"""
    cleaned = _MIMO_BLOCK_RE.sub("", text or "")
    return cleaned.strip()
