"""PDF 文件有效性校验。"""
from __future__ import annotations

from pathlib import Path


def is_valid_pdf_bytes(content: bytes) -> bool:
    return len(content) >= 4 and content[:4] == b"%PDF"


def is_valid_pdf_file(path: str | Path) -> bool:
    try:
        with open(path, "rb") as f:
            return is_valid_pdf_bytes(f.read(4))
    except OSError:
        return False


def is_pdf_load_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    name = type(exc).__name__.lower()
    return "pdfium" in name or "data format error" in text or "failed to load document" in text
