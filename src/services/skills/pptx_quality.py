"""paper2ppt 产物质量检查：页数、占位内容等。"""
from __future__ import annotations

import re
from pathlib import Path

DEFAULT_SLIDE_TARGET = 12
MIN_SLIDE_COUNT = 10
MAX_SLIDE_COUNT = 20

_SLIDE_COUNT_RE = re.compile(
    r"(\d+)\s*(?:张|页|slides?|页幻灯片|张幻灯片|张ppt|页ppt)",
    re.IGNORECASE,
)


def parse_target_slide_count(query: str, *, default: int = DEFAULT_SLIDE_TARGET) -> int:
    """从用户问题解析目标页数，默认 12（技能 workflow 推荐 10–16）。"""
    text = query or ""
    hits: list[int] = []
    for m in _SLIDE_COUNT_RE.finditer(text):
        try:
            hits.append(int(m.group(1)))
        except ValueError:
            continue
    if hits:
        # 取最后一次明确提到的页数（如先概述后说「规划了13张」）
        target = hits[-1]
        return max(MIN_SLIDE_COUNT, min(MAX_SLIDE_COUNT, target))
    return default


def min_required_slides(target: int) -> int:
    """允许略少于规划，但不得低于技能下限。"""
    return max(MIN_SLIDE_COUNT, target - 2)


def validate_pptx_file(path: Path, *, min_slides: int) -> list[str]:
    """检查已生成的 PPTX 是否满足最低页数。"""
    errors: list[str] = []
    if not path.is_file():
        return [f"PPTX 未生成：{path.as_posix()}"]
    try:
        from pptx import Presentation

        prs = Presentation(str(path))
        count = len(prs.slides)
    except Exception as exc:
        return [f"无法读取 PPTX：{exc}"]

    if count < min_slides:
        errors.append(
            f"PPTX 仅 {count} 张幻灯片，少于要求的 {min_slides} 张；"
            "请按论文内容补全结构化页面（标题、背景、方法、结果、讨论、结论等）"
        )
    return errors
