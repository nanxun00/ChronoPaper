"""从 MinerU 生成的 Markdown 提取标题、作者、摘要等元数据。"""
from __future__ import annotations

import json
import re
from pathlib import Path


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _strip_html(text: str) -> str:
    text = re.sub(r"<sup>[^<]*</sup>", "", text or "")
    return re.sub(r"<[^>]+>", "", text)


def _heading_text(line: str) -> str | None:
    match = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
    if not match:
        return None
    return match.group(2).strip()


def _normalize_heading(text: str) -> str:
    return re.sub(r"[^A-Za-z]", "", text or "").upper()


def _is_abstract_heading(text: str) -> bool:
    return _normalize_heading(text) == "ABSTRACT"


def _is_image_line(line: str) -> bool:
    return bool(re.match(r"^!\[", line.strip()))


def _is_affiliation_line(line: str) -> bool:
    stripped = line.strip()
    return bool(re.match(r"^<sup>[^<]+</sup>\s+\S", stripped))


def title_from_markdown(text: str) -> str:
    for line in (text or "").splitlines():
        match = re.match(r"^#\s+(.+)$", line.strip())
        if match:
            return _clean_text(match.group(1))
    return ""


def authors_from_markdown(text: str) -> str:
    """提取标题后、第一个二级标题前的作者行（跳过图片与机构地址）。"""
    passed_title = False
    author_lines: list[str] = []

    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        if re.match(r"^#\s+", stripped) and not passed_title:
            passed_title = True
            continue
        if not passed_title:
            continue

        if _heading_text(stripped) is not None:
            break
        if _is_image_line(stripped):
            continue
        if _is_affiliation_line(stripped):
            break

        author_lines.append(stripped)

    if not author_lines:
        return ""

    raw = _strip_html(", ".join(author_lines))
    names: list[str] = []
    for segment in raw.split(","):
        name = _clean_text(segment)
        name = re.sub(r"\s+[a-z](?:,\*)?$", "", name, flags=re.IGNORECASE).strip()
        name = re.sub(r"\*+$", "", name).strip()
        if name:
            names.append(name)
    return ", ".join(names)


def abstract_from_markdown(text: str, max_len: int = 2000) -> str:
    """提取 ## ABSTRACT / ## A B S T R A C T 段落，至下一个二级标题为止。"""
    in_abstract = False
    chunks: list[str] = []

    for line in (text or "").splitlines():
        stripped = line.strip()
        heading = _heading_text(stripped)
        if heading is not None:
            if in_abstract:
                break
            if _is_abstract_heading(heading):
                in_abstract = True
            continue

        if not in_abstract:
            continue
        if not stripped or _is_image_line(stripped):
            continue

        cleaned = _strip_html(stripped)
        cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
        if cleaned:
            chunks.append(cleaned)
        if len(" ".join(chunks)) >= max_len:
            break

    return _clean_text(" ".join(chunks))[:max_len]


def metadata_from_markdown(text: str) -> dict[str, str]:
    return {
        "title": title_from_markdown(text),
        "authors": authors_from_markdown(text),
        "abstract": abstract_from_markdown(text),
    }


def apply_upload_metadata_from_md(paper, md_path: str) -> None:
    """用 MinerU 的 content.md 回填本地上传论文的标题、作者与摘要。"""
    if getattr(paper, "source", None) != "upload":
        return

    md_text = Path(md_path).read_text(encoding="utf-8")
    meta = metadata_from_markdown(md_text)
    if meta.get("title"):
        paper.title = meta["title"]
    if meta.get("abstract"):
        paper.abstract = meta["abstract"]
    if meta.get("authors"):
        names = [n.strip() for n in meta["authors"].split(",") if n.strip()]
        paper.authors = json.dumps(names, ensure_ascii=False)
