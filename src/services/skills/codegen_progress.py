"""Codegen 执行过程进度事件，供聊天流式推送到前端。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

CODE_PREVIEW_MAX = 8000

ProgressCallback = Callable[["CodegenProgressEvent"], None]


@dataclass
class CodegenProgressEvent:
    phase: str
    round: int = 0
    message: str = ""
    code_preview: str | None = None
    script_rel: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "phase": self.phase,
            "round": self.round,
            "message": self.message,
        }
        if self.code_preview:
            out["code_preview"] = self.code_preview
        if self.script_rel:
            out["script_rel"] = self.script_rel
        return out


def truncate_code_preview(code: str | None, limit: int = CODE_PREVIEW_MAX) -> str | None:
    if not code:
        return None
    text = code.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 40] + "\n\n# …（脚本已截断，完整版见技能目录）"


def emit_progress(callback: ProgressCallback | None, event: CodegenProgressEvent) -> None:
    if callback is None:
        return
    try:
        callback(event)
    except Exception:
        pass
