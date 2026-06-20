"""Skill Agent：LLM + read 工具循环。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from src.services.skills.agent.tool_parser import parse_tool_calls, strip_tool_calls
from src.services.skills.agent.tools import execute_tool, format_tool_results
from src.utils.logging_config import setup_logger

logger = setup_logger("SkillAgent")

DEFAULT_MAX_STEPS = 5
_TOOL_MARKER = "<function="


@dataclass
class SkillAgentResult:
    content: str
    steps: int = 0
    tool_calls_total: int = 0


@dataclass
class AgentStreamEvent:
    """Agent 流式事件：token 为面向用户的累积文本；tool_step 表示正在读文件。"""

    kind: str  # "token" | "tool_step" | "done"
    content: str = ""
    result: SkillAgentResult | None = None


def _extract_llm_text(message: Any) -> str:
    if hasattr(message, "content"):
        return str(message.content or "")
    if isinstance(message, dict):
        return str(message.get("content") or "")
    return str(message or "")


def _extract_delta_piece(delta: Any) -> str:
    if delta is None:
        return ""
    if hasattr(delta, "content"):
        piece = delta.content
        return str(piece) if piece else ""
    if isinstance(delta, dict):
        return str(delta.get("content") or "")
    return str(delta or "")


def _user_visible_prefix(text: str) -> str:
    """工具调用出现前的用户可见文本（不含未闭合的工具块）。"""
    idx = (text or "").find(_TOOL_MARKER)
    segment = text[:idx] if idx >= 0 else text
    return strip_tool_calls(segment)


def run_skill_agent(
    model: Any,
    messages: list[dict],
    skill_root: Path,
    *,
    max_steps: int = DEFAULT_MAX_STEPS,
) -> SkillAgentResult:
    """
    在已有 system + 历史 + 用户消息上运行 Agent 循环。
    messages 不会被原地修改；返回面向用户的最终文本。
    """
    result = SkillAgentResult(content="")
    for event in iter_skill_agent(
        model,
        messages,
        skill_root,
        max_steps=max_steps,
        stream=False,
    ):
        if event.kind == "done" and event.result is not None:
            result = event.result
    return result


def iter_skill_agent(
    model: Any,
    messages: list[dict],
    skill_root: Path,
    *,
    max_steps: int = DEFAULT_MAX_STEPS,
    stream: bool = True,
) -> Iterator[AgentStreamEvent]:
    """
    运行 Agent 并在最终回复阶段流式产出 token。
    tool 步骤不向前端推送 LLM 正文，仅产出 tool_step 事件。
    """
    msgs = [dict(m) for m in messages]
    tool_calls_total = 0
    last_text = ""

    for step in range(max_steps):
        if step > 0:
            yield AgentStreamEvent(kind="tool_step")

        last_text = ""
        last_visible = ""
        if stream:
            for delta in model.predict(msgs, stream=True):
                piece = _extract_delta_piece(delta)
                if not piece:
                    continue
                last_text += piece
                visible = _user_visible_prefix(last_text)
                if len(visible) > len(last_visible):
                    last_visible = visible
                    yield AgentStreamEvent(kind="token", content=visible)
        else:
            last_text = _extract_llm_text(model.predict(msgs, stream=False))

        msgs.append({"role": "assistant", "content": last_text})

        calls = parse_tool_calls(last_text)
        if not calls:
            final = strip_tool_calls(last_text) or last_text
            result = SkillAgentResult(
                content=final.strip(),
                steps=step + 1,
                tool_calls_total=tool_calls_total,
            )
            yield AgentStreamEvent(kind="done", content=result.content, result=result)
            return

        tool_calls_total += len(calls)
        results = [execute_tool(skill_root, call) for call in calls]
        tool_msg = format_tool_results(results)
        msgs.append({"role": "user", "content": tool_msg})
        logger.debug(
            "Skill agent step %d: %d tool call(s) on %s",
            step + 1,
            len(calls),
            skill_root.name,
        )

    final = strip_tool_calls(last_text) or last_text
    if parse_tool_calls(final):
        final = (
            "抱歉，读取技能参考文档时步骤过多未能完成。"
            "请简化问题后重试，或检查技能包内文件路径是否正确。"
        )
    result = SkillAgentResult(
        content=final.strip(),
        steps=max_steps,
        tool_calls_total=tool_calls_total,
    )
    yield AgentStreamEvent(kind="done", content=result.content, result=result)
