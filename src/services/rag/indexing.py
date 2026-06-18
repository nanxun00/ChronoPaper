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

_SECTION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "abstract": ("abstract", "summary", "摘要"),
    "intro": ("introduction", "background", "引言", "背景"),
    "method": ("method", "methodology", "approach", "model", "方法", "模型"),
    "experiment": ("experiment", "evaluation", "result", "实验", "评估", "结果"),
    "conclusion": ("conclusion", "discussion", "结论", "讨论"),
    "reference": ("reference", "bibliography", "参考文献"),
}


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


def _split_long_text(text: str, base_meta: dict[str, Any], *, chunk_size: int, chunk_overlap: int) -> list[dict[str, Any]]:
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
    chunks: list[dict[str, Any]] = []
    current_section = "text"
    kw_json = json.dumps(keywords or [], ensure_ascii=False)

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

        base = {
            "kb_id": kb_id,
            "paper_id": paper_id,
            "doc_id": doc_id,
            "resource_type": resource_type,
            "owner_user_id": owner_user_id,
            "year": year,
            "ccf_rank": ccf_rank,
            "task_domain": task_domain,
            "keywords": kw_json,
            "page_num": int(block.get("page_idx", 0)) + 1 if block.get("page_idx") is not None else None,
            "bbox": _bbox_to_str(block),
            "section_type": current_section,
            "block_type": block_type,
        }
        chunks.extend(
            _split_long_text(text, base, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        )
    return chunks


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
