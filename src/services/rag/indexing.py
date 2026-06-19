"""文本分块：MinerU content_list 论文专用 + 兼容旧 plain chunk。"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from llama_index.core import Document
from llama_index.core.node_parser import SentenceSplitter

from src.utils import hashstr
from src.utils.snowflake import next_snowflake_id

DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 20
LONG_SPLIT_THRESHOLD = 500
MIN_STANDALONE_LEN = 50
MIN_NON_CORE_LEN = 80

HIGH_VALUE_SECTIONS = frozenset({"abstract", "intro", "method", "experiment", "conclusion"})
HIGH_VALUE_BLOCK_TYPES = frozenset({"table", "equation", "figure"})
TABLE_MAX_CHUNK_LEN = 20_000
EQUATION_MAX_CHUNK_LEN = 2_000

_SECTION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "abstract": ("abstract", "summary", "摘要"),
    "intro": ("introduction", "background", "引言", "背景"),
    "method": ("method", "methodology", "approach", "model", "方法", "模型"),
    "experiment": ("experiment", "evaluation", "result", "实验", "评估", "结果"),
    "conclusion": ("conclusion", "discussion", "结论", "讨论"),
    "reference": ("reference", "bibliography", "参考文献"),
}

_PURE_DIGIT_RE = re.compile(r"^\d{1,4}$")
_SEPARATOR_RE = re.compile(r"^[-_=·•\s]{2,}$")
_SUPERSCRIPT_ONLY_RE = re.compile(r"^[\d*,\s†‡§¹²³⁴⁵⁶⁷⁸⁹⁰]+$")
_COPYRIGHT_RE = re.compile(
    r"(©|copyright|all rights reserved|creativecommons|open access|under a\s+cc\s)",
    re.I,
)
_DOI_LINE_RE = re.compile(r"^(https?://)?(dx\.)?doi\.org/[\w./-]+", re.I)
_DATE_LINE_RE = re.compile(
    r"^(received|revised|accepted|available online|article history).{0,40}\d{4}",
    re.I,
)
_BOILERPLATE_RE = re.compile(
    r"(CRediT\s+authorship|author contributions|funding|grant\s+no|"
    r"conflict of interest|declarations of competing|acknowledgements?|"
    r"data availability|ethics approval|informed consent)",
    re.I,
)
_AUTHOR_BIO_RE = re.compile(
    r"(biograph(y|ical)?|received (his|her) (b\.?s\.?|m\.?s\.?|ph\.?d\.?)|"
    r"is (currently )?(a|an) (professor|researcher|lecturer) (at|with))",
    re.I,
)
_JOURNAL_HEADER_RE = re.compile(
    r"^(neurocomputing|elsevier|springer|ieee|acm|nature)\b.*(\(\d{4}\)|vol\.|volume)",
    re.I,
)
_JOURNAL_BOILERPLATE_RE = re.compile(
    r"(contents lists available|journal homepage|sciencedirect|elsevier\.com/locate)",
    re.I,
)
_RUNNING_HEADER_RE = re.compile(r"^[.\s]*[A-Z]\.\s+[\w\s,]+\bet al\.\s*$", re.I)
_RUNNING_HEADER_ET_AL_RE = re.compile(
    r"^(?:[.\s]*)?(?:[A-Z]\.\s+)?[\w\s,.']+\bet\s+al\.?\s*$",
    re.I,
)
_NUMBERED_HEADER_RE = re.compile(r"^\d+(?:\.\d+)*\.?\s+\S")
_FIGURE_CAPTION_RE = re.compile(r"^Fig\.?\s*\d+", re.I)
_TABLE_LABEL_RE = re.compile(r"^Table\s+\d+", re.I)
_AFFILIATION_RE = re.compile(
    r"(university|school of|department|institute|laboratory|college|hospital|"
    r"center for|academy|ueestc|uestc)",
    re.I,
)
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")
_CORRESPONDING_RE = re.compile(r"corresponding author", re.I)


class _PreparedBlock:
    __slots__ = ("text", "block_type", "section_type", "page_num", "bbox", "drop")

    def __init__(
        self,
        text: str,
        *,
        block_type: str,
        section_type: str,
        page_num: int | None,
        bbox: str | None,
        drop: bool = False,
    ) -> None:
        self.text = text
        self.block_type = block_type
        self.section_type = section_type
        self.page_num = page_num
        self.bbox = bbox
        self.drop = drop


def _infer_section_from_title(title: str) -> str | None:
    t = (title or "").lower()
    for section, keys in _SECTION_KEYWORDS.items():
        if any(k in t for k in keys):
            return section
    return None


def _block_text(block: dict[str, Any]) -> str:
    if block.get("text"):
        return str(block["text"]).strip()
    if block.get("list_items"):
        return "\n".join(str(x).strip() for x in block["list_items"] if str(x).strip())
    if block.get("table_body"):
        return str(block["table_body"]).strip()
    if block.get("content"):
        return str(block["content"]).strip()
    caps = block.get("image_caption") or block.get("table_caption") or block.get("chart_caption")
    if isinstance(caps, list) and caps:
        return "\n".join(str(c).strip() for c in caps if str(c).strip())
    return ""


def _map_block_type(block: dict[str, Any]) -> str:
    raw = str(block.get("type") or "text").lower()
    text = _block_text(block)
    if _FIGURE_CAPTION_RE.match(text.strip()):
        return "figure"
    if raw in {"title", "text", "table", "equation", "list", "code", "chart", "image"}:
        if raw == "list":
            return "list"
        if raw in {"equation"}:
            return "equation"
        if raw in {"table", "chart"}:
            return "table"
        if block.get("text_level"):
            return "title"
        return raw if raw in {"title", "text", "table", "equation"} else "text"
    return "text"


def _bbox_to_str(block: dict[str, Any]) -> str | None:
    bbox = block.get("bbox")
    if not bbox:
        return None
    if isinstance(bbox, list):
        return ",".join(str(int(x)) for x in bbox[:4])
    return str(bbox)


def _effective_len(text: str) -> int:
    return len(re.sub(r"\s+", "", text or ""))


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _is_table_fragment(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if t.startswith("<table") or "</table>" in t:
        return True
    if re.search(r"</tr>|<td[\s>]", t, re.I):
        return True
    if re.search(r"±\s*[\d.{\\}]", t) and ("</td>" in t or "<td" in t):
        return True
    return False


def _is_table_like_block(blk: _PreparedBlock) -> bool:
    if blk.block_type == "table":
        return True
    return _is_table_fragment(blk.text)


def _is_figure_caption_text(text: str) -> bool:
    return bool(_FIGURE_CAPTION_RE.match((text or "").strip()))


def _is_boilerplate_short_line(text: str) -> bool:
    plain = _strip_html(text)
    compact = _effective_len(plain)
    if compact < 8:
        return True
    if _JOURNAL_BOILERPLATE_RE.search(plain):
        return True
    if _RUNNING_HEADER_RE.match(plain):
        return True
    if _RUNNING_HEADER_ET_AL_RE.match(plain):
        return True
    if compact < 60 and _EMAIL_RE.search(plain) and "corresponding" not in plain.lower():
        return True
    if compact < 48 and plain.lower() in {"neurocomputing"}:
        return True
    return False


def _is_author_line(text: str) -> bool:
    t = _strip_html(text)
    if not t or len(t) > 280:
        return False
    if _EMAIL_RE.search(t) or _CORRESPONDING_RE.search(t):
        return True
    normalized = re.sub(r"[¹²³⁴⁵⁶⁷⁸⁹⁰†‡§*]+", "", t)
    if re.search(
        r"^[A-Z][\w\-'.]+(?:\s+[A-Z][\w\-'.]+){0,4}(?:\s*[,，]\s*[A-Z][\w\-'.]+(?:\s+[A-Z][\w\-'.]+){0,3})+",
        normalized,
    ):
        return True
    if "," in t and len(t) < 200 and re.search(r"[A-Z][a-z]+\s+[A-Z]", normalized):
        return True
    return False


def _is_affiliation_line(text: str) -> bool:
    t = _strip_html(text)
    if not t or len(t) > 320:
        return False
    return bool(_AFFILIATION_RE.search(t))


def _is_front_matter_line(text: str, block_type: str) -> bool:
    if block_type == "title":
        return True
    plain = _strip_html(text)
    if not plain:
        return False
    if _is_author_line(text) or _is_affiliation_line(text):
        return True
    if re.search(r"<sup>", text, re.I) and (_AFFILIATION_RE.search(plain) or "," in plain):
        return True
    return False


def _should_drop_block(text: str, block_type: str, section_type: str) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    if _is_table_fragment(t):
        return False
    compact = _effective_len(t)

    if _PURE_DIGIT_RE.match(t):
        return True
    if _SEPARATOR_RE.match(t):
        return True
    if _SUPERSCRIPT_ONLY_RE.match(t):
        return True
    if _COPYRIGHT_RE.search(t) and compact < 220:
        return True
    if _DOI_LINE_RE.match(t) and compact < 120:
        return True
    if _DATE_LINE_RE.match(t):
        return True
    if _BOILERPLATE_RE.search(t) and section_type != "method":
        return True
    if _AUTHOR_BIO_RE.search(t) and compact < 420 and section_type != "reference":
        return True
    if _is_boilerplate_short_line(t):
        return True
    if compact < MIN_STANDALONE_LEN and _JOURNAL_HEADER_RE.match(t):
        return True
    if _RUNNING_HEADER_ET_AL_RE.match(_strip_html(t)):
        return True
    if compact < MIN_STANDALONE_LEN and re.match(r"^https?://", t, re.I):
        return True
    if block_type == "text" and compact < MIN_STANDALONE_LEN:
        if not _is_author_line(t) and not _is_affiliation_line(t):
            if section_type not in HIGH_VALUE_SECTIONS:
                return True
    return False


def _prepare_blocks(content_list: list[dict[str, Any]]) -> list[_PreparedBlock]:
    prepared: list[_PreparedBlock] = []
    current_section = "text"

    for block in content_list:
        if not isinstance(block, dict):
            continue
        text = _block_text(block)
        if not text:
            continue

        block_type = _map_block_type(block)
        if block_type == "title":
            inferred = _infer_section_from_title(text)
            if inferred:
                current_section = inferred

        if _should_drop_block(text, block_type, current_section):
            continue

        prepared.append(
            _PreparedBlock(
                text,
                block_type=block_type,
                section_type=current_section,
                page_num=int(block.get("page_idx", 0)) + 1 if block.get("page_idx") is not None else None,
                bbox=_bbox_to_str(block),
            )
        )
    return prepared


def _merge_front_matter(blocks: list[_PreparedBlock]) -> list[_PreparedBlock]:
    if not blocks:
        return blocks

    out: list[_PreparedBlock] = []
    i = 0
    while i < len(blocks):
        blk = blocks[i]
        if blk.section_type in HIGH_VALUE_SECTIONS or blk.section_type == "reference":
            out.append(blk)
            i += 1
            continue

        if blk.block_type in HIGH_VALUE_BLOCK_TYPES:
            out.append(blk)
            i += 1
            continue

        if blk.block_type == "title" or (i == 0 and _is_front_matter_line(blk.text, blk.block_type)):
            parts = [blk.text]
            page_num = blk.page_num
            bbox = blk.bbox
            j = i + 1
            while j < len(blocks):
                nxt = blocks[j]
                if nxt.section_type in HIGH_VALUE_SECTIONS or nxt.section_type == "reference":
                    break
                if nxt.block_type in HIGH_VALUE_BLOCK_TYPES:
                    break
                if nxt.block_type == "title" and _infer_section_from_title(nxt.text):
                    break
                if not _is_front_matter_line(nxt.text, nxt.block_type):
                    break
                parts.append(nxt.text)
                j += 1

            merged_text = "\n".join(p for p in parts if p.strip())
            if _effective_len(merged_text) >= MIN_STANDALONE_LEN:
                out.append(
                    _PreparedBlock(
                        merged_text,
                        block_type="title",
                        section_type="title",
                        page_num=page_num,
                        bbox=bbox,
                    )
                )
            i = j
            continue

        out.append(blk)
        i += 1
    return out


def _is_section_header_text(text: str, block_type: str) -> bool:
    t = (text or "").strip()
    if not t or len(t) > 80:
        return False
    if block_type == "title":
        return True
    if _NUMBERED_HEADER_RE.match(t):
        return True
    if len(t) < 60 and re.match(r"^\d*\.?\s*\w", t):
        return True
    return False


def _merge_section_headers(blocks: list[_PreparedBlock]) -> list[_PreparedBlock]:
    """将 Abstract/Introduction 等短标题与紧随其后的正文合并。"""
    if not blocks:
        return blocks

    out: list[_PreparedBlock] = []
    i = 0
    while i < len(blocks):
        blk = blocks[i]
        if not _is_section_header_text(blk.text, blk.block_type):
            out.append(blk)
            i += 1
            continue

        parts = [blk.text.strip()]
        page_num = blk.page_num
        bbox = blk.bbox
        section = blk.section_type
        j = i + 1
        while j < len(blocks):
            nxt = blocks[j]
            if nxt.section_type not in {section, "text"}:
                break
            if _is_section_header_text(nxt.text, nxt.block_type):
                parts.append(nxt.text.strip())
                j += 1
                continue
            if nxt.block_type in {"text", "title"} and not _is_table_like_block(nxt):
                parts.append(nxt.text.strip())
                j += 1
            break

        if len(parts) > 1:
            out.append(
                _PreparedBlock(
                    "\n".join(p for p in parts if p),
                    block_type="text",
                    section_type=section,
                    page_num=page_num,
                    bbox=bbox,
                )
            )
            i = j
            continue
        out.append(blk)
        i += 1
    return out


def _merge_consecutive_tables(blocks: list[_PreparedBlock]) -> list[_PreparedBlock]:
    """整张表格（含 MinerU 拆出的 HTML 行片段）合并为一个 chunk。"""
    if not blocks:
        return blocks

    out: list[_PreparedBlock] = []
    i = 0
    while i < len(blocks):
        blk = blocks[i]
        if not _is_table_like_block(blk):
            out.append(blk)
            i += 1
            continue

        parts = [blk.text.strip()]
        page_num = blk.page_num
        section = blk.section_type
        bbox = blk.bbox
        j = i + 1
        while j < len(blocks):
            nxt = blocks[j]
            if _is_table_like_block(nxt):
                parts.append(nxt.text.strip())
                j += 1
                continue
            if (
                nxt.block_type == "text"
                and nxt.section_type == section
                and _TABLE_LABEL_RE.match(nxt.text.strip())
                and len(nxt.text) < 700
            ):
                parts.append(nxt.text.strip())
                j += 1
                continue
            break

        out.append(
            _PreparedBlock(
                "\n".join(p for p in parts if p),
                block_type="table",
                section_type=section,
                page_num=page_num,
                bbox=bbox,
            )
        )
        i = j
    return out


def _merge_figure_captions(blocks: list[_PreparedBlock]) -> list[_PreparedBlock]:
    """图题与前后紧邻正文合并，避免 Fig.N 单独成块。"""
    if not blocks:
        return blocks

    out: list[_PreparedBlock] = []
    i = 0
    while i < len(blocks):
        blk = blocks[i]
        is_caption = blk.block_type == "figure" or (
            blk.block_type in {"text", "table"} and _is_figure_caption_text(blk.text) and len(blk.text) < 320
        )
        if is_caption:
            caption = blk.text.strip()
            if out and out[-1].section_type == blk.section_type and out[-1].block_type in {"text", "table", "figure"}:
                prev = out[-1]
                prev.text = f"{prev.text}\n{caption}".strip()
                if prev.block_type == "table" and _is_figure_caption_text(caption):
                    prev.block_type = "text"
                i += 1
                continue
            if i + 1 < len(blocks) and blocks[i + 1].section_type == blk.section_type:
                nxt = blocks[i + 1]
                if nxt.block_type == "text" and not _is_figure_caption_text(nxt.text):
                    out.append(
                        _PreparedBlock(
                            f"{caption}\n{nxt.text.strip()}".strip(),
                            block_type="text",
                            section_type=blk.section_type,
                            page_num=blk.page_num,
                            bbox=blk.bbox,
                        )
                    )
                    i += 2
                    continue
        elif (
            blk.block_type == "text"
            and re.search(r"\bFig\.?\s*\d+", blk.text, re.I)
            and not _is_figure_caption_text(blk.text)
            and i + 1 < len(blocks)
            and blocks[i + 1].section_type == blk.section_type
            and _is_figure_caption_text(blocks[i + 1].text)
        ):
            out.append(
                _PreparedBlock(
                    f"{blk.text.strip()}\n{blocks[i + 1].text.strip()}".strip(),
                    block_type="text",
                    section_type=blk.section_type,
                    page_num=blk.page_num,
                    bbox=blk.bbox,
                )
            )
            i += 2
            continue
        out.append(blk)
        i += 1
    return out


def _merge_equation_context(blocks: list[_PreparedBlock]) -> list[_PreparedBlock]:
    """公式与前后紧邻说明合并为方法类正文块。"""
    if not blocks:
        return blocks

    out: list[_PreparedBlock] = []
    i = 0
    while i < len(blocks):
        blk = blocks[i]
        if blk.block_type != "equation":
            out.append(blk)
            i += 1
            continue

        parts: list[str] = []
        if (
            out
            and out[-1].block_type == "text"
            and out[-1].section_type in {"method", "experiment", "intro"}
            and len(out[-1].text) < 900
        ):
            parts.append(out.pop().text)
        parts.append(blk.text.strip())
        j = i + 1
        if (
            j < len(blocks)
            and blocks[j].block_type == "text"
            and blocks[j].section_type == blk.section_type
            and len(blocks[j].text) < 500
            and not _is_table_like_block(blocks[j])
        ):
            parts.append(blocks[j].text.strip())
            j += 1

        out.append(
            _PreparedBlock(
                "\n\n".join(p for p in parts if p),
                block_type="text",
                section_type=blk.section_type,
                page_num=blk.page_num,
                bbox=blk.bbox,
            )
        )
        i = j
    return out


def _merge_author_bios(blocks: list[_PreparedBlock]) -> list[_PreparedBlock]:
    """参考文献区作者简介合并为一个大块。"""
    if not blocks:
        return blocks

    out: list[_PreparedBlock] = []
    i = 0
    while i < len(blocks):
        blk = blocks[i]
        if blk.section_type == "reference" and (
            _AUTHOR_BIO_RE.search(blk.text) or (len(blk.text) < 320 and re.search(r"received (his|her)", blk.text, re.I))
        ):
            parts = ["作者简介"]
            page_num = blk.page_num
            bbox = blk.bbox
            j = i
            while j < len(blocks) and blocks[j].section_type == "reference":
                cur = blocks[j]
                if _AUTHOR_BIO_RE.search(cur.text) or (
                    len(cur.text) < 360
                    and re.search(r"(professor|researcher|ph\.?d|university|received)", cur.text, re.I)
                ):
                    parts.append(cur.text.strip())
                    j += 1
                    continue
                if j == i:
                    break
                break
            if len(parts) > 1:
                out.append(
                    _PreparedBlock(
                        "\n".join(parts),
                        block_type="text",
                        section_type="reference",
                        page_num=page_num,
                        bbox=bbox,
                    )
                )
                i = j
                continue
        out.append(blk)
        i += 1
    return out


def _merge_adjacent_short_lines(blocks: list[_PreparedBlock]) -> list[_PreparedBlock]:
    """短碎行并入相邻正文（页眉页脚、单行图注等）。"""
    if not blocks:
        return blocks

    out: list[_PreparedBlock] = []
    for blk in blocks:
        if _is_core_block(blk) or blk.block_type in {"table", "figure"}:
            out.append(blk)
            continue
        if _effective_len(blk.text) >= MIN_NON_CORE_LEN:
            out.append(blk)
            continue
        if _is_boilerplate_short_line(blk.text):
            if out and out[-1].block_type == "text":
                continue
            continue
        if out and out[-1].section_type == blk.section_type:
            out[-1].text = f"{out[-1].text}\n{blk.text.strip()}".strip()
            continue
        if out:
            out[-1].text = f"{out[-1].text}\n{blk.text.strip()}".strip()
            continue
        out.append(blk)
    return out


def _is_core_block(blk: _PreparedBlock) -> bool:
    if blk.section_type in HIGH_VALUE_SECTIONS or blk.section_type == "title":
        return True
    if blk.block_type in HIGH_VALUE_BLOCK_TYPES:
        return True
    return False


def _merge_orphan_section_headers(blocks: list[_PreparedBlock]) -> list[_PreparedBlock]:
    """极短编号标题（如 3. Methods）并入下一块。"""
    if not blocks:
        return blocks

    out: list[_PreparedBlock] = []
    i = 0
    while i < len(blocks):
        blk = blocks[i]
        if (
            _NUMBERED_HEADER_RE.match(blk.text.strip())
            and len(blk.text.strip()) < 36
            and i + 1 < len(blocks)
            and not _is_table_like_block(blocks[i + 1])
        ):
            nxt = blocks[i + 1]
            merged_type = "text" if nxt.block_type in {"text", "title", "equation"} else nxt.block_type
            out.append(
                _PreparedBlock(
                    f"{blk.text.strip()}\n{nxt.text.strip()}".strip(),
                    block_type=merged_type,
                    section_type=blk.section_type,
                    page_num=blk.page_num,
                    bbox=blk.bbox,
                )
            )
            i += 2
            continue
        out.append(blk)
        i += 1
    return out


def _merge_short_non_core(blocks: list[_PreparedBlock]) -> list[_PreparedBlock]:
    if not blocks:
        return blocks

    merged: list[_PreparedBlock] = []
    for blk in blocks:
        if _is_core_block(blk) or _effective_len(blk.text) >= MIN_NON_CORE_LEN:
            merged.append(blk)
            continue
        if merged and not _is_core_block(merged[-1]):
            prev = merged[-1]
            prev.text = f"{prev.text}\n{blk.text}".strip()
            continue
        if merged:
            prev = merged[-1]
            prev.text = f"{prev.text}\n{blk.text}".strip()
            continue
        merged.append(blk)

    out: list[_PreparedBlock] = []
    i = 0
    while i < len(merged):
        blk = merged[i]
        if not _is_core_block(blk) and _effective_len(blk.text) < MIN_NON_CORE_LEN:
            if i + 1 < len(merged):
                nxt = merged[i + 1]
                nxt.text = f"{blk.text}\n{nxt.text}".strip()
                i += 1
                continue
            if out:
                out[-1].text = f"{out[-1].text}\n{blk.text}".strip()
                i += 1
                continue
        out.append(blk)
        i += 1
    return out


def _split_long_text(
    text: str,
    base_meta: dict[str, Any],
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> list[dict[str, Any]]:
    if len(text) <= chunk_size:
        item = dict(base_meta)
        item["chunk_text"] = text
        item["chunk_id"] = next_snowflake_id()
        item["text_hash"] = hashstr(text, with_salt=True)
        return [item]
    splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    nodes = splitter.get_nodes_from_documents([Document(text=text)])
    out: list[dict[str, Any]] = []
    for node in nodes:
        piece = (node.text or "").strip()
        if not piece:
            continue
        item = dict(base_meta)
        item["chunk_text"] = piece
        item["chunk_id"] = next_snowflake_id()
        item["text_hash"] = hashstr(piece, with_salt=True)
        out.append(item)
    return out


def _emit_chunks(
    blocks: list[_PreparedBlock],
    *,
    kb_id: str,
    paper_id: str | None,
    doc_id: str | None,
    resource_type: str,
    owner_user_id: str,
    year: int | None,
    ccf_rank: str | None,
    task_domain: str | None,
    keywords: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for blk in blocks:
        if blk.drop or not blk.text.strip():
            continue
        base = {
            "kb_id": kb_id,
            "paper_id": paper_id,
            "doc_id": doc_id,
            "resource_type": resource_type,
            "owner_user_id": owner_user_id,
            "year": year,
            "ccf_rank": ccf_rank,
            "task_domain": task_domain,
            "keywords": keywords,
            "page_num": blk.page_num,
            "bbox": blk.bbox,
            "section_type": blk.section_type,
            "block_type": blk.block_type,
        }
        split_threshold = chunk_size
        if blk.block_type == "table":
            split_threshold = TABLE_MAX_CHUNK_LEN
        elif blk.block_type == "equation":
            split_threshold = EQUATION_MAX_CHUNK_LEN
        elif _is_core_block(blk):
            split_threshold = LONG_SPLIT_THRESHOLD
        chunks.extend(
            _split_long_text(
                blk.text,
                base,
                chunk_size=split_threshold,
                chunk_overlap=chunk_overlap,
            )
        )
    return chunks


def chunk_paper_content_list(
    content_list: list[dict[str, Any]],
    *,
    kb_id: str,
    paper_id: str | None = None,
    doc_id: str | None = None,
    resource_type: str = "public",
    owner_user_id: str = "0",
    year: int | None = None,
    ccf_rank: str | None = None,
    task_domain: str | None = None,
    keywords: list[str] | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[dict[str, Any]]:
    """MinerU content_list → 带完整元数据的分块列表（不含向量）。"""
    kw_json = json.dumps(keywords or [], ensure_ascii=False)
    prepared = _prepare_blocks(content_list)
    prepared = _merge_front_matter(prepared)
    prepared = _merge_section_headers(prepared)
    prepared = _merge_consecutive_tables(prepared)
    prepared = _merge_figure_captions(prepared)
    prepared = _merge_equation_context(prepared)
    prepared = _merge_author_bios(prepared)
    prepared = _merge_adjacent_short_lines(prepared)
    prepared = _merge_orphan_section_headers(prepared)
    prepared = _merge_short_non_core(prepared)
    return _emit_chunks(
        prepared,
        kb_id=kb_id,
        paper_id=paper_id,
        doc_id=doc_id,
        resource_type=resource_type,
        owner_user_id=owner_user_id,
        year=year,
        ccf_rank=ccf_rank,
        task_domain=task_domain,
        keywords=kw_json,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )


def load_content_list(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    raise ValueError(f"Invalid content_list format: {p}")


def chunk(text_or_path, params=None):
    """兼容旧接口：plain 文本 / uploads 文件简单分块（非 MinerU 结构）。"""
    params = params or {}
    chunk_size = int(params.get("chunk_size", DEFAULT_CHUNK_SIZE))
    chunk_overlap = int(params.get("chunk_overlap", DEFAULT_CHUNK_OVERLAP))
    splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    if os.path.isfile(text_or_path) and "uploads" in str(text_or_path):
        from llama_index.core.node_parser import SimpleFileNodeParser
        from llama_index.readers.file import DocxReader, FlatReader

        file_type = Path(text_or_path).suffix.lower()
        if file_type in [".txt", ".json", ".md"]:
            docs = FlatReader().load_data(Path(text_or_path))
        elif file_type in [".docx"]:
            docs = DocxReader().load_data(Path(text_or_path))
        else:
            raise ValueError(f"Unsupported file type `{file_type}`")
        if params.get("use_parser"):
            parser = SimpleFileNodeParser()
            return parser.get_nodes_from_documents(docs)
        return splitter.get_nodes_from_documents(docs)

    docs = [Document(id_=hashstr(str(text_or_path)), text=str(text_or_path))]
    return splitter.get_nodes_from_documents(docs)
