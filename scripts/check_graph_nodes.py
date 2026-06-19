#!/usr/bin/env python
"""检查图谱节点领域与描述字段。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

NAMES = ["t1", "t2", "dice", "structuralsimilarityindex", "bratsdataset", "tissnet"]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    from src.services.rag.startup import startup
    from src.services.graph.neo4j_store import PaperGraphStore

    store = PaperGraphStore(startup.dbm.graph_base.driver, startup.dbm.graph_base.kgdb_name)
    with store._session() as session:
        for name in NAMES:
            row = session.run(
                """
                MATCH (n)
                WHERE n.name = $name
                RETURN labels(n) AS labels,
                       n.task_domain AS task_domain,
                       n.task AS task,
                       n.applicable_task AS applicable_task,
                       n.description AS description,
                       n.kb_id AS kb_id
                LIMIT 1
                """,
                name=name,
            ).single()
            if not row:
                print(f"--- {name}: NOT FOUND")
                continue
            labels = row["labels"]
            domain = row["task_domain"] or row["task"] or row["applicable_task"] or ""
            print(f"--- {name} ({labels[0] if labels else '?'})")
            print(f"    domain: {domain!r}")
            print(f"    description: {(row['description'] or '')[:120]!r}")
            print(f"    kb_id: {row['kb_id']}")

        paper = session.run(
            """
            MATCH (p:Paper {paper_id: $pid, kb_id: $kb})
            RETURN p.task_domain AS domain
            """,
            pid="doi:10.1016_j.neucom.2023.126295",
            kb="318358647963648",
        ).single()
        print(f"\nTISS-net Paper task_domain: {paper['domain']!r}" if paper else "\nPaper not found")

        datasets = session.run(
            """
            MATCH (p:Paper {paper_id: $pid, kb_id: $kb})-[r:USE_DATASET]->(d:Dataset)
            RETURN d.name AS name
            ORDER BY name
            """,
            pid="doi:10.1016_j.neucom.2023.126295",
            kb="318358647963648",
        ).data()
        print("\nTISS-net USE_DATASET:", [r["name"] for r in datasets])

        stats = session.run(
            """
            MATCH (n)
            WHERE n:Model OR n:Dataset OR n:Metric
            RETURN labels(n)[0] AS type,
                   count(n) AS total,
                   sum(CASE WHEN coalesce(n.description, '') = '' THEN 1 ELSE 0 END) AS no_desc,
                   sum(CASE WHEN coalesce(n.task_domain, n.task, n.applicable_task, '') =~ '.*[A-Za-z]{4,}.*' THEN 1 ELSE 0 END) AS maybe_en
            """
        ).data()
        print("\nEntity stats:")
        for s in stats:
            print(f"  {s}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
