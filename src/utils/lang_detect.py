"""简单语言检测（用于抓取前自动翻译）。"""
from __future__ import annotations

import re

_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")


def contains_chinese(text: str) -> bool:
    return bool(_CJK_RE.search(text or ""))
