#!/usr/bin/env python
"""删除论文向量并重新入库（测试新分块规则）。

用法::

    python scripts/reindex_paper.py --paper-id doi:10.1016_j.neucom.2023.126295 --kb-id 318358647963648
    python scripts/reindex_paper.py --delete-only
    python scripts/reindex_paper.py --reindex-only
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_PAPER_ID = "doi:10.1016_j.neucom.2023.126295"
DEFAULT_KB_ID = "318358647963648"


def _paper_chunk_stats(session, kb_id: str, paper_id: str) -> dict:
    from src.models.rag import TextChunk

    rows = (
        session.query(TextChunk)
        .filter(
            TextChunk.kb_id == kb_id,
            TextChunk.paper_id == paper_id,
            TextChunk.is_deleted == 0,
        )
        .all()
    )
    short = [r for r in rows if len((r.chunk_text or "").strip()) < 80]
    by_block: dict[str, int] = {}
    by_section: dict[str, int] = {}
    for r in rows:
        by_block[r.block_type or "unknown"] = by_block.get(r.block_type or "unknown", 0) + 1
        by_section[r.section_type or "unknown"] = by_section.get(r.section_type or "unknown", 0) + 1
    samples = [
        {
            "chunk_id": r.chunk_id,
            "block_type": r.block_type,
            "section_type": r.section_type,
            "len": len(r.chunk_text or ""),
            "preview": (r.chunk_text or "")[:120],
        }
        for r in sorted(rows, key=lambda x: (x.page_num or 0, x.chunk_id))[:8]
    ]
    return {
        "total": len(rows),
        "short_lt_80": len(short),
        "by_block_type": by_block,
        "by_section_type": by_section,
        "samples": samples,
    }


def delete_paper_vectors(paper_id: str, kb_id: str) -> dict:
    from src.models.base import SessionLocal
    from src.services.rag.indexing_pipeline import soft_delete_paper_chunks
    from src.services.rag.startup import startup

    kb = startup.dbm.knowledge_base
    if not kb:
        raise RuntimeError("Knowledge base / Milvus not available")

    session = SessionLocal()
    try:
        before = _paper_chunk_stats(session, kb_id, paper_id)
        deleted = soft_delete_paper_chunks(session, kb, kb_id=kb_id, paper_id=paper_id)
        after = _paper_chunk_stats(session, kb_id, paper_id)
        return {"deleted": deleted, "before": before, "after": after}
    finally:
        session.close()


def reindex_paper(paper_id: str, kb_id: str, owner_user_id: str = "0", *, skip_graph: bool = False) -> dict:
    from src.models.base import SessionLocal
    from src.models.literature import Paper
    from src.models.rag import KnowledgeBaseRecord
    from src.services.rag.indexing import chunk_paper_content_list, load_content_list
    from src.services.rag.indexing_pipeline import index_chunk_rows
    from src.services.rag import mineru_indexing
    from src.services.rag.startup import startup

    session = SessionLocal()
    try:
        paper = session.query(Paper).filter(Paper.arxiv_id == paper_id).first()
        if not paper:
            return {"status": "missing_paper"}
        kb_row = session.query(KnowledgeBaseRecord).filter(KnowledgeBaseRecord.kb_id == kb_id).first()
        if not kb_row:
            return {"status": "missing_kb"}

        content_list_path = mineru_indexing.resolve_paper_content_list_path(paper_id)
        if not content_list_path:
            return {"status": "missing_content_list", "hint": "请先完成 MinerU 解析"}

        blocks = load_content_list(content_list_path)
        year = paper.published_at.year if paper.published_at else None
        rows = chunk_paper_content_list(
            blocks,
            kb_id=kb_id,
            paper_id=paper_id,
            resource_type="public",
            owner_user_id=owner_user_id,
            year=year,
            ccf_rank=paper.venue_rank,
            task_domain=None,
            keywords=paper.categories_list() if hasattr(paper, "categories_list") else [],
        )
        kb = startup.dbm.knowledge_base
        count = index_chunk_rows(session, kb, rows)
        paper.parse_status = "indexed"
        session.add(paper)
        session.commit()

        graph_result = None
        if startup.config.enable_knowledge_graph and not skip_graph:
            from src.services.graph.graph_index_service import index_paper_graph

            graph_result = index_paper_graph(paper_id, kb_id=kb_id, owner_user_id=owner_user_id)

        after = _paper_chunk_stats(session, kb_id, paper_id)
        return {
            "status": "ok",
            "chunks_indexed": count,
            "after": after,
            "graph": graph_result,
        }
    finally:
        session.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="删除论文向量并重新入库")
    parser.add_argument("--paper-id", default=DEFAULT_PAPER_ID)
    parser.add_argument("--kb-id", default=DEFAULT_KB_ID)
    parser.add_argument("--delete-only", action="store_true")
    parser.add_argument("--reindex-only", action="store_true")
    parser.add_argument("--skip-graph", action="store_true", help="仅重入向量，不重建图谱")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paper_id = args.paper_id
    kb_id = args.kb_id

    if not args.reindex_only:
        print("=== 删除旧向量 ===")
        print(json.dumps(delete_paper_vectors(paper_id, kb_id), ensure_ascii=False, indent=2))

    if not args.delete_only:
        print("=== 重新入库 ===")
        print(json.dumps(reindex_paper(paper_id, kb_id, skip_graph=args.skip_graph), ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
