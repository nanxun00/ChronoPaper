#!/usr/bin/env python
"""GraphRAG Phase 2 端到端验证脚本。

用法（项目根目录）::

    python scripts/verify_graphrag_phase2.py check
    python scripts/verify_graphrag_phase2.py cite
    python scripts/verify_graphrag_phase2.py retrieve
    python scripts/verify_graphrag_phase2.py all

    python scripts/verify_graphrag_phase2.py cite --paper-id doi:10.1016_j.neucom.2023.126295 --kb-id 318358647963648

Windows PowerShell 建议先设置::

    $env:PYTHONNOUSERSITE="1"
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

RETRIEVE_QUERIES = [
    "TISS-net 模型的改进关系",
    "脑肿瘤分割领域 SOTA 模型有哪些",
    "TISS-net 的引用关系",
]


def _json(data) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def check_neo4j(paper_id: str, kb_id: str) -> dict:
    from src.services.graph.neo4j_store import PaperGraphStore
    from src.services.rag.startup import startup

    store = PaperGraphStore(startup.dbm.graph_base.driver, startup.dbm.graph_base.kgdb_name)
    with store._session() as session:
        paper = session.run(
            "MATCH (p:Paper {paper_id: $pid, kb_id: $kb}) RETURN p.title AS t, p.task_domain AS td",
            pid=paper_id,
            kb=kb_id,
        ).single()
        cite_kb = session.run(
            "MATCH (:Paper {kb_id: $kb})-[r:CITE]->(:Paper {kb_id: $kb}) RETURN count(r) AS c",
            kb=kb_id,
        ).single()
        out_c = session.run(
            "MATCH (p:Paper {paper_id: $pid, kb_id: $kb})-[r:CITE]->() RETURN count(r) AS c",
            pid=paper_id,
            kb=kb_id,
        ).single()
        in_c = session.run(
            "MATCH ()-[r:CITE]->(p:Paper {paper_id: $pid, kb_id: $kb}) RETURN count(r) AS c",
            pid=paper_id,
            kb=kb_id,
        ).single()
        models = session.run(
            "MATCH (:Paper {kb_id: $kb})-[:PROPOSE]->(m:Model) RETURN m.name AS name LIMIT 8",
            kb=kb_id,
        ).data()
    return {
        "paper_id": paper_id,
        "kb_id": kb_id,
        "paper": dict(paper) if paper else None,
        "cite_edges_kb": cite_kb["c"] if cite_kb else 0,
        "outgoing": out_c["c"] if out_c else 0,
        "incoming": in_c["c"] if in_c else 0,
        "models": models,
    }


def run_cite_sync(paper_id: str, kb_id: str) -> dict:
    from src.models.base import SessionLocal
    from src.models.literature import Paper
    from src.services.graph.cite_sync import sync_paper_citations
    from src.services.graph.neo4j_store import PaperGraphStore
    from src.services.rag.startup import startup

    session = SessionLocal()
    try:
        paper = session.query(Paper).filter(Paper.arxiv_id == paper_id).first()
        if not paper:
            return {"status": "missing_paper", "paper_id": paper_id}
        store = PaperGraphStore(startup.dbm.graph_base.driver, startup.dbm.graph_base.kgdb_name)
        return sync_paper_citations(
            store,
            session,
            paper,
            kb_id=kb_id,
            owner_user_id="0",
            is_private=False,
        )
    finally:
        session.close()


def test_retriever(query: str, kb_id: str | None = None) -> dict:
    from src.services.rag.retriever import Retriever
    from src.services.rag.startup import startup

    retriever = Retriever(startup.config, startup.dbm, startup.model)
    meta = {
        "use_graph": True,
        "use_knowledge_base": False,
        "db_name": None,
        "user_id": 0,
    }
    if kb_id:
        row = startup.dbm.knowledge_base.get_database_info(kb_id) if startup.dbm.knowledge_base else None
        if row and isinstance(row, dict):
            meta["db_name"] = row.get("metaname")

    refs = retriever.retrieval(query, [], meta)
    gb = refs.get("graph_base", {}).get("results", {})
    return {
        "query": query,
        "entities": refs.get("entities"),
        "nodes": len(gb.get("nodes") or []),
        "edges": len(gb.get("edges") or []),
        "chunks": len(gb.get("chunks") or []),
        "chain_summary": (gb.get("chain_summary") or "")[:200],
        "sota_summary": (gb.get("sota_summary") or "")[:400],
        "cite_summary": (gb.get("cite_summary") or "")[:400],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GraphRAG Phase 2 验证")
    parser.add_argument(
        "action",
        choices=("check", "cite", "retrieve", "all"),
        help="check=Neo4j 状态; cite=同步 CITE; retrieve=检索链路; all=全部",
    )
    parser.add_argument("--paper-id", default=DEFAULT_PAPER_ID, help="论文 paper_id (arxiv_id)")
    parser.add_argument("--kb-id", default=DEFAULT_KB_ID, help="知识库 kb_id")
    parser.add_argument(
        "--query",
        action="append",
        dest="queries",
        help="retrieve 时自定义问题，可重复传入",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paper_id = args.paper_id
    kb_id = args.kb_id
    queries = args.queries or RETRIEVE_QUERIES

    if args.action in ("check", "all"):
        print("=== Neo4j ===")
        print(_json(check_neo4j(paper_id, kb_id)))

    if args.action in ("cite", "all"):
        print("=== Cite sync ===")
        print(_json(run_cite_sync(paper_id, kb_id)))
        print("=== Neo4j after cite ===")
        print(_json(check_neo4j(paper_id, kb_id)))

    if args.action in ("retrieve", "all"):
        for query in queries:
            print(f"=== Retriever: {query} ===")
            print(_json(test_retriever(query, kb_id)))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
