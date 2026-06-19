"""Neo4j Phase 1 论文图谱写入与查询。"""
from __future__ import annotations

from typing import Any

from src.utils.logging_config import setup_logger

logger = setup_logger("PaperGraphStore")

ENTITY_LABELS = frozenset({"Paper", "Model", "Dataset", "Metric", "Venue"})
GRAPH_REL_TYPES = frozenset(
    {
        "PROPOSE",
        "IMPROVE_FROM",
        "DIFFERENT_WITH",
        "USE_DATASET",
        "EVALUATE_BY",
        "EXTEND_FROM",
        "PUBLISH_AT",
        "CITE",
    }
)


def _merge_ids(existing: list | None, new_ids: list[str]) -> list[str]:
    merged = list(existing or [])
    for cid in new_ids:
        if cid and cid not in merged:
            merged.append(cid)
    return merged


class PaperGraphStore:
    def __init__(self, driver, database: str = "neo4j") -> None:
        self.driver = driver
        self.database = database

    def _session(self):
        return self.driver.session(database=self.database)

    def ensure_indexes(self) -> None:
        statements = [
            "CREATE INDEX paper_graph_paper_id IF NOT EXISTS FOR (p:Paper) ON (p.paper_id, p.kb_id)",
            "CREATE INDEX paper_graph_model_name IF NOT EXISTS FOR (m:Model) ON (m.name)",
            "CREATE INDEX paper_graph_dataset_name IF NOT EXISTS FOR (d:Dataset) ON (d.name)",
            "CREATE INDEX paper_graph_metric_name IF NOT EXISTS FOR (m:Metric) ON (m.name)",
        ]
        with self._session() as session:
            for stmt in statements:
                try:
                    session.run(stmt)
                except Exception as exc:
                    logger.debug("Index create skipped: %s", exc)

    def upsert_paper(
        self,
        *,
        paper_id: str,
        kb_id: str,
        title: str,
        year: int | None,
        venue: str | None,
        ccf_rank: str | None,
        task_domain: str | None,
        innovation_summary: str,
        related_chunk_ids: list[str],
        is_private: bool,
        owner_user_id: str,
        keywords: list[str] | None = None,
    ) -> None:
        def _write(tx, props):
            tx.run(
                """
                MERGE (p:Paper {paper_id: $paper_id, kb_id: $kb_id})
                SET p.title = $title,
                    p.name = $name,
                    p.year = $year,
                    p.venue = $venue,
                    p.ccf_rank = $ccf_rank,
                    p.task_domain = $task_domain,
                    p.innovation_summary = $innovation_summary,
                    p.is_private = $is_private,
                    p.owner_user_id = $owner_user_id,
                    p.keywords = $keywords,
                    p.related_chunk_ids = $related_chunk_ids
                """,
                **props,
            )

        with self._session() as session:
            existing = session.execute_read(
                lambda tx: tx.run(
                    "MATCH (p:Paper {paper_id: $pid, kb_id: $kb}) RETURN p.related_chunk_ids AS ids LIMIT 1",
                    pid=paper_id,
                    kb=kb_id,
                ).single()
            )
            prev_ids = (existing or {}).get("ids") if existing else None
            merged_ids = _merge_ids(prev_ids, related_chunk_ids)
            display_name = (title or paper_id or "").strip()
            if len(display_name) > 64:
                display_name = display_name[:64] + "..."
            session.execute_write(
                _write,
                {
                    "paper_id": paper_id,
                    "kb_id": kb_id,
                    "title": title or "",
                    "name": display_name,
                    "year": year,
                    "venue": venue or "",
                    "ccf_rank": ccf_rank or "None",
                    "task_domain": task_domain or "",
                    "innovation_summary": innovation_summary or "",
                    "is_private": bool(is_private),
                    "owner_user_id": str(owner_user_id or "0"),
                    "keywords": keywords or [],
                    "related_chunk_ids": merged_ids,
                },
            )

    def upsert_named_entity(
        self,
        label: str,
        *,
        name: str,
        kb_id: str,
        ref_chunk_ids: list[str],
        extra: dict[str, Any] | None = None,
    ) -> None:
        if label not in {"Model", "Dataset", "Metric", "Venue"}:
            return
        extra = extra or {}

        def _write(tx):
            row = tx.run(
                f"MATCH (n:{label} {{name: $name}}) RETURN n.ref_chunk_ids AS ids LIMIT 1",
                name=name,
            ).single()
            merged_ids = _merge_ids(row["ids"] if row else None, ref_chunk_ids)
            params = {"name": name, "kb_id": kb_id, "ref_chunk_ids": merged_ids, **extra}
            set_parts = ["n.kb_id = $kb_id", "n.ref_chunk_ids = $ref_chunk_ids"]
            for key in extra:
                set_parts.append(f"n.{key} = ${key}")
            tx.run(
                f"MERGE (n:{label} {{name: $name}}) SET " + ", ".join(set_parts),
                **params,
            )

        with self._session() as session:
            session.execute_write(_write)

    def merge_relationship(
        self,
        rel_type: str,
        *,
        source_label: str,
        target_label: str,
        source_key: str,
        target_key: str,
        source_match: dict[str, Any],
        target_match: dict[str, Any],
        kb_id: str,
        chunk_id: str | None = None,
    ) -> None:
        if rel_type not in GRAPH_REL_TYPES:
            return

        def _write(tx):
            if source_label == "Paper":
                src = tx.run(
                    "MATCH (s:Paper {paper_id: $sk, kb_id: $kb_id}) RETURN elementId(s) AS id LIMIT 1",
                    sk=source_key,
                    kb_id=kb_id,
                ).single()
            else:
                src = tx.run(
                    f"MATCH (s:{source_label} {{name: $sk}}) RETURN elementId(s) AS id LIMIT 1",
                    sk=source_key,
                ).single()
            if target_label == "Paper":
                tgt = tx.run(
                    "MATCH (t:Paper {paper_id: $tk, kb_id: $kb_id}) RETURN elementId(t) AS id LIMIT 1",
                    tk=target_key,
                    kb_id=kb_id,
                ).single()
            else:
                tgt = tx.run(
                    f"MATCH (t:{target_label} {{name: $tk}}) RETURN elementId(t) AS id LIMIT 1",
                    tk=target_key,
                ).single()
            if not src or not tgt:
                return
            tx.run(
                f"""
                MATCH (s), (t)
                WHERE elementId(s) = $sid AND elementId(t) = $tid
                MERGE (s)-[r:{rel_type}]->(t)
                SET r.kb_id = $kb_id, r.ref_chunk_id = coalesce($chunk_id, r.ref_chunk_id)
                """,
                sid=src["id"],
                tid=tgt["id"],
                kb_id=kb_id,
                chunk_id=chunk_id,
            )

        with self._session() as session:
            session.execute_write(_write)

    def write_static_metadata_relations(
        self,
        *,
        paper_id: str,
        kb_id: str,
        venue: str | None,
        venue_rank: str | None,
        venue_type: str | None,
    ) -> None:
        with self._session() as session:
            session.run(
                """
                MATCH (p:Paper {paper_id: $pid, kb_id: $kb})-[r:WRITTEN_BY]->(:Author)
                DELETE r
                """,
                pid=paper_id,
                kb=kb_id,
            )
        venue_name = (venue or "").strip()
        if venue_name:
            self.upsert_named_entity(
                "Venue",
                name=venue_name,
                kb_id=kb_id,
                ref_chunk_ids=[],
                extra={"ccf_rank": venue_rank or "None", "type": venue_type or ""},
            )
            self.merge_relationship(
                "PUBLISH_AT",
                source_label="Paper",
                target_label="Venue",
                source_key=paper_id,
                target_key=venue_name,
                source_match={"paper_id": paper_id},
                target_match={"name": venue_name},
                kb_id=kb_id,
            )

    def query_temporal_chain(
        self,
        model_names: list[str],
        *,
        kb_id: str,
        user_id: str | int,
        limit: int = 20,
    ) -> dict[str, Any]:
        """按 Model 名称查询 IMPROVE_FROM 时序链及关联 chunk。"""
        if not model_names:
            return {"models": [], "edges": [], "chunk_ids": [], "papers": []}

        uid = str(user_id or "0")
        cypher = """
        UNWIND $names AS model_name
        MATCH (m:Model {name: model_name})
        OPTIONAL MATCH (pred:Model)-[:IMPROVE_FROM*1..8]->(m)
        OPTIONAL MATCH (m)-[:IMPROVE_FROM*1..8]->(succ:Model)
        WITH m, collect(DISTINCT pred) AS preds, collect(DISTINCT succ) AS succs
        UNWIND (preds + succs + [m]) AS node
        WITH DISTINCT node AS model
        WHERE model IS NOT NULL
        OPTIONAL MATCH (p:Paper)-[:PROPOSE]->(model)
        WHERE p.kb_id = $kb_id
          AND (NOT coalesce(p.is_private, false) OR p.owner_user_id = $uid)
        WITH model, collect(DISTINCT p) AS papers
        RETURN model.name AS name,
               model.task_domain AS task_domain,
               model.birth_year AS birth_year,
               model.ref_chunk_ids AS ref_chunk_ids,
               [x IN papers WHERE x IS NOT NULL | x.paper_id] AS paper_ids
        LIMIT $limit
        """
        edge_cypher = """
        UNWIND $names AS model_name
        MATCH (m:Model {name: model_name})
        OPTIONAL MATCH (a:Model)-[r:IMPROVE_FROM]->(b:Model)
        WHERE a.name = m.name OR b.name = m.name
           OR (a)-[:IMPROVE_FROM*1..8]-(m)
        RETURN DISTINCT a.name AS source, b.name AS target, type(r) AS rel_type, r.ref_chunk_id AS chunk_id
        LIMIT $limit
        """
        with self._session() as session:
            models = list(session.run(cypher, names=model_names, kb_id=kb_id, uid=uid, limit=limit))
            edges = list(session.run(edge_cypher, names=model_names, limit=limit * 3))

        chunk_ids: list[str] = []
        model_rows = []
        for rec in models:
            row = dict(rec)
            model_rows.append(row)
            for cid in row.get("ref_chunk_ids") or []:
                if cid not in chunk_ids:
                    chunk_ids.append(cid)

        edge_rows = []
        for rec in edges:
            row = dict(rec)
            if not row.get("source"):
                continue
            edge_rows.append(row)
            cid = row.get("chunk_id")
            if cid and cid not in chunk_ids:
                chunk_ids.append(cid)

        return {
            "models": model_rows,
            "edges": edge_rows,
            "chunk_ids": chunk_ids,
            "papers": [],
        }

    def find_models_by_keyword(
        self,
        keyword: str,
        *,
        kb_id: str,
        user_id: str | int,
        limit: int = 5,
    ) -> list[str]:
        from src.services.graph.entity_normalize import clean_entity_name

        uid = str(user_id or "0")
        raw = keyword.strip().lower()
        cleaned = clean_entity_name(keyword)
        cypher = """
        MATCH (p:Paper {kb_id: $kb_id})-[:PROPOSE]->(m:Model)
        WHERE (NOT coalesce(p.is_private, false) OR p.owner_user_id = $uid)
          AND (
            m.name = $kw
            OR m.name = $clean
            OR m.name CONTAINS $kw
            OR m.name CONTAINS $clean
            OR $clean CONTAINS m.name
          )
        RETURN DISTINCT m.name AS name
        LIMIT $limit
        """
        with self._session() as session:
            rows = session.run(
                cypher,
                kb_id=kb_id,
                uid=uid,
                kw=raw,
                clean=cleaned,
                limit=limit,
            )
            return [r["name"] for r in rows if r.get("name")]

    def list_task_domains(
        self,
        *,
        kb_id: str,
        user_id: str | int,
        limit: int = 20,
    ) -> list[str]:
        uid = str(user_id or "0")
        cypher = """
        MATCH (p:Paper {kb_id: $kb_id})
        WHERE (NOT coalesce(p.is_private, false) OR p.owner_user_id = $uid)
          AND coalesce(p.task_domain, '') <> ''
        RETURN DISTINCT p.task_domain AS domain
        LIMIT $limit
        """
        with self._session() as session:
            rows = session.run(cypher, kb_id=kb_id, uid=uid, limit=limit)
            return [r["domain"] for r in rows if r.get("domain")]

    def delete_kb_graph(self, kb_id: str) -> dict[str, int]:
        """删除知识库在 Neo4j 中的 Paper 节点及 kb_id 关联边。"""
        with self._session() as session:
            rel_row = session.run(
                """
                MATCH ()-[r]->()
                WHERE r.kb_id = $kb
                WITH collect(r) AS rels
                FOREACH (x IN rels | DELETE x)
                RETURN size(rels) AS c
                """,
                kb=kb_id,
            ).single()
            rel_deleted = int(rel_row["c"]) if rel_row else 0

            paper_row = session.run(
                """
                MATCH (p:Paper {kb_id: $kb})
                WITH collect(p) AS nodes
                FOREACH (n IN nodes | DETACH DELETE n)
                RETURN size(nodes) AS c
                """,
                kb=kb_id,
            ).single()
            paper_deleted = int(paper_row["c"]) if paper_row else 0

        logger.info("deleted kb graph kb=%s papers=%s rels=%s", kb_id, paper_deleted, rel_deleted)
        return {"papers": paper_deleted, "relationships": rel_deleted}

    def query_sota_models(
        self,
        *,
        task_domain: str,
        kb_id: str,
        user_id: str | int,
        limit: int = 10,
    ) -> dict[str, Any]:
        """领域 SOTA：按 task_domain 聚合 Model + Dataset + Metric + 提出论文。"""
        if not task_domain:
            return {"models": [], "chunk_ids": [], "papers": []}

        uid = str(user_id or "0")
        domain = task_domain.strip().lower()
        cypher = """
        MATCH (p:Paper {kb_id: $kb_id})-[:PROPOSE]->(m:Model)
        WHERE (NOT coalesce(p.is_private, false) OR p.owner_user_id = $uid)
          AND (
            toLower(coalesce(p.task_domain, '')) CONTAINS $domain
            OR toLower(coalesce(m.task_domain, '')) CONTAINS $domain
          )
        OPTIONAL MATCH (p)-[:USE_DATASET]->(d:Dataset)
        OPTIONAL MATCH (p)-[:EVALUATE_BY]->(metric:Metric)
        WITH m, p, collect(DISTINCT d.name) AS datasets, collect(DISTINCT metric.name) AS metrics
        RETURN m.name AS model,
               m.birth_year AS year,
               m.ref_chunk_ids AS ref_chunk_ids,
               p.paper_id AS paper_id,
               p.title AS paper_title,
               p.year AS paper_year,
               datasets,
               metrics
        ORDER BY coalesce(m.birth_year, p.year, 0) DESC
        LIMIT $limit
        """
        with self._session() as session:
            rows = [dict(r) for r in session.run(cypher, kb_id=kb_id, uid=uid, domain=domain, limit=limit)]

        chunk_ids: list[str] = []
        for row in rows:
            for cid in row.get("ref_chunk_ids") or []:
                if cid not in chunk_ids:
                    chunk_ids.append(cid)

        return {"models": rows, "chunk_ids": chunk_ids, "task_domain": task_domain}

    def query_citation_network(
        self,
        paper_ids: list[str],
        *,
        kb_id: str,
        user_id: str | int,
        hops: int = 2,
        limit: int = 30,
    ) -> dict[str, Any]:
        """引用脉络：CITE 双向扩展。"""
        if not paper_ids:
            return {"papers": [], "edges": [], "chunk_ids": []}

        uid = str(user_id or "0")
        hops = max(1, min(int(hops), 3))
        cypher = f"""
        UNWIND $paper_ids AS pid
        MATCH (p:Paper {{paper_id: pid, kb_id: $kb_id}})
        WHERE NOT coalesce(p.is_private, false) OR p.owner_user_id = $uid
        OPTIONAL MATCH path = (p)-[:CITE*1..{hops}]-(other:Paper {{kb_id: $kb_id}})
        WITH collect(DISTINCT p) + collect(DISTINCT other) AS ps
        UNWIND ps AS paper
        WITH DISTINCT paper
        WHERE paper IS NOT NULL
        RETURN paper.paper_id AS paper_id,
               paper.title AS title,
               paper.name AS name,
               paper.year AS year,
               paper.related_chunk_ids AS related_chunk_ids
        LIMIT $limit
        """
        edge_cypher = """
        UNWIND $paper_ids AS pid
        MATCH (a:Paper {kb_id: $kb_id})-[r:CITE]->(b:Paper {kb_id: $kb_id})
        WHERE a.paper_id = pid OR b.paper_id = pid
        RETURN DISTINCT a.paper_id AS source, a.name AS source_name,
               b.paper_id AS target, b.name AS target_name, type(r) AS rel_type
        LIMIT $limit
        """
        with self._session() as session:
            papers = [dict(r) for r in session.run(cypher, paper_ids=paper_ids, kb_id=kb_id, uid=uid, limit=limit)]
            edges = [dict(r) for r in session.run(edge_cypher, paper_ids=paper_ids, kb_id=kb_id, uid=uid, limit=limit)]

        chunk_ids: list[str] = []
        for row in papers:
            for cid in row.get("related_chunk_ids") or []:
                if cid not in chunk_ids:
                    chunk_ids.append(cid)

        return {"papers": papers, "edges": edges, "chunk_ids": chunk_ids}
