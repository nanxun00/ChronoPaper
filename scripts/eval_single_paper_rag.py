#!/usr/bin/env python
"""单文献 RAG 评测：检索 → LLM 生成真实回答 → LLM 评判四指标。

用法（项目根目录）::

    python scripts/eval_single_paper_rag.py
    python scripts/eval_single_paper_rag.py --ids V1,G2,VG1
    python scripts/eval_single_paper_rag.py --links vector,both --dry-run

Windows PowerShell::

    $env:PYTHONNOUSERSITE="1"
    python scripts/eval_single_paper_rag.py --output scripts/single_paper_rag_qa_eval.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

KB_ID = "318358647963648"
DEFAULT_INPUT = ROOT / "scripts" / "single_paper_rag_qa_eval.json"
DEFAULT_OUTPUT = ROOT / "scripts" / "single_paper_rag_qa_eval.json"
LINKS = ("vector", "graph", "both")

JUDGE_PROMPT = """你是 RAG 系统评测员。请根据「标准答案」和「检索上下文」对「系统回答」打分。

<用户问题>
{query}
</用户问题>

<检索上下文（系统可见资料）>
{context}
</检索上下文>

<标准答案>
{reference}
</标准答案>

<系统回答>
{answer}
</系统回答>

评分标准：
1. answer_correctness（0~1）：事实是否与标准答案一致，允许表述不同。
2. hallucination_rate（0~1）：回答中无法从检索上下文推出的错误陈述占比，越低越好。
3. answer_relevance（1~5）：是否紧扣用户问题，5=完全切题。
4. completeness（0~1）：是否覆盖标准答案中的关键要点。

只输出一个 JSON 对象，不要其他文字：
{{"answer_correctness":0.0,"hallucination_rate":0.0,"answer_relevance":0.0,"completeness":0.0,"brief_reason":"一句话说明"}}"""


def _resolve_db_name(dbm) -> str | None:
    row = dbm.resolve_kb(KB_ID)
    if row:
        return row.metaname
    try:
        return dbm.ensure_default_knowledge_base().metaname
    except Exception:
        return None


def _extract_context_from_prompt(prompt: str) -> str:
    m = re.search(r"<参考资料>：\s*(.*?)\s*</参考资料>", prompt, re.DOTALL)
    if m:
        return m.group(1).strip()[:6000]
    return prompt[:6000]


def _kb_snippet(refs) -> str:
    lines = []
    for r in refs.get("knowledge_base", {}).get("results") or []:
        ent = r.get("entity") or {}
        cid = ent.get("chunk_id") or r.get("id")
        text = str(ent.get("text") or "")[:600]
        lines.append(f"[向量chunk {cid}]\n{text}")
    return "\n\n".join(lines)


def _graph_snippet(refs) -> str:
    gb = refs.get("graph_base", {}).get("results") or {}
    parts = []
    for key in ("chain_summary", "sota_summary", "cite_summary"):
        if gb.get(key):
            parts.append(f"[{key}]\n{gb[key]}")
    for e in (gb.get("edges") or [])[:20]:
        parts.append(
            f"{e.get('source_name')} --{e.get('type')}--> {e.get('target_name')}"
        )
    for c in (gb.get("chunks") or [])[:6]:
        parts.append(f"[图谱chunk {c.get('chunk_id')}]\n{str(c.get('chunk_text') or '')[:500]}")
    return "\n".join(parts)


def _retrieval_stats(refs) -> dict:
    gb = refs.get("graph_base", {}).get("results") or {}
    kb = refs.get("knowledge_base", {}).get("results") or []
    return {
        "kb_hits": len(kb),
        "graph_nodes": len(gb.get("nodes") or []),
        "graph_edges": len(gb.get("edges") or []),
        "graph_chunks": len(gb.get("chunks") or []),
        "has_chain": bool(gb.get("chain_summary")),
        "has_sota": bool(gb.get("sota_summary")),
        "has_cite": bool(gb.get("cite_summary")),
        "entities": refs.get("entities") or [],
    }


def _parse_json_block(text: str) -> dict:
    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return {}


def _normalize_metrics(raw: dict) -> dict:
    def _f(key, lo, hi, default):
        try:
            v = float(raw.get(key, default))
        except (TypeError, ValueError):
            v = default
        return round(max(lo, min(hi, v)), 2)

    return {
        "answer_correctness": _f("answer_correctness", 0, 1, 0.5),
        "hallucination_rate": _f("hallucination_rate", 0, 1, 0.3),
        "answer_relevance": _f("answer_relevance", 1, 5, 3.0),
        "completeness": _f("completeness", 0, 1, 0.5),
        "judge_reason": str(raw.get("brief_reason") or raw.get("reason") or "").strip(),
    }


def _generate_answer(retriever, model, query: str, meta: dict) -> tuple[str, dict, str]:
    prompt, refs = retriever(query, [], meta)
    resp = model.predict(prompt, stream=False)
    content = getattr(resp, "content", None) or str(resp)
    context = _extract_context_from_prompt(prompt)
    return content.strip(), refs, context


def _judge_answer(model, query: str, reference: str, answer: str, context: str) -> dict:
    prompt = JUDGE_PROMPT.format(
        query=query,
        reference=reference,
        answer=answer,
        context=context[:5000] or "（无检索上下文）",
    )
    resp = model.predict(prompt, stream=False)
    content = getattr(resp, "content", None) or str(resp)
    return _normalize_metrics(_parse_json_block(content))


def _meta_for_link(link: str, db_name: str | None) -> dict:
    use_graph = link in ("graph", "both")
    use_kb = link in ("vector", "both")
    meta = {
        "use_graph": use_graph,
        "enable_retrieval": True,
        "db_name": db_name if use_kb else None,
        "user_id": 0,
        "maxQueryCount": 10,
        "topK": 5,
        "distanceThreshold": 0,
        "rerankThreshold": 0.0,
        "rewriteQuery": "",
    }
    if not use_kb:
        meta["kbOptOut"] = True
    return meta


def _summarize(items: list[dict], link: str, id_prefix: str) -> dict:
    subset = [
        item["responses"][link]["metrics"]
        for item in items
        if item["id"].startswith(id_prefix) and link == item.get("primary_link", "")
    ]
    if not subset and id_prefix:
        subset = [
            item["responses"][link]["metrics"]
            for item in items
            if item["id"].startswith(id_prefix)
        ]
    if not subset:
        return {}
    n = len(subset)
    return {
        "count": n,
        "answer_correctness_avg": round(sum(m["answer_correctness"] for m in subset) / n, 2),
        "hallucination_rate_avg": round(sum(m["hallucination_rate"] for m in subset) / n, 2),
        "answer_relevance_avg": round(sum(m["answer_relevance"] for m in subset) / n, 1),
        "completeness_avg": round(sum(m["completeness"] for m in subset) / n, 2),
    }


def run_eval(
    *,
    input_path: Path,
    output_path: Path,
    ids: list[str] | None,
    links: list[str],
    skip_judge: bool,
    dry_run: bool,
) -> dict:
    data = json.loads(input_path.read_text(encoding="utf-8"))
    items = data.get("items") or []
    if ids:
        id_set = set(ids)
        items = [it for it in items if it["id"] in id_set]

    from src.services.rag.startup import startup

    db_name = _resolve_db_name(startup.dbm)
    retriever = startup.retriever
    model = startup.model

    print(f"db_name={db_name}, model={getattr(model, 'model_name', '?')}, items={len(items)}", flush=True)

    for item in items:
        q = item["question"]
        ref = item["reference_answer"]
        if "responses" not in item:
            item["responses"] = {}

        for link in links:
            print(f"\n[{item['id']}] link={link} generating...", flush=True)
            meta = _meta_for_link(link, db_name)

            if dry_run:
                item["responses"][link] = {
                    "answer": "(dry-run)",
                    "metrics": {},
                    "retrieval": {},
                    "context_preview": "",
                }
                continue

            answer, refs, context = _generate_answer(retriever, model, q, meta)
            stats = _retrieval_stats(refs)

            metrics = {}
            if not skip_judge:
                print(f"  judging...", flush=True)
                metrics = _judge_answer(model, q, ref, answer, context)

            item["responses"][link] = {
                "answer": answer,
                "metrics": metrics,
                "retrieval": stats,
                "context_preview": context[:1200],
            }
            print(f"  kb={stats['kb_hits']} graph_nodes={stats['graph_nodes']} AC={metrics.get('answer_correctness')}", flush=True)

    data["meta"]["eval_date"] = str(date.today())
    data["meta"]["eval_pipeline"] = "retrieval → LLM answer → LLM judge"
    data["meta"]["note"] = (
        "responses.*.answer 为检索上下文注入后由配置 LLM 真实生成；"
        "metrics 由同一 LLM 对照标准答案与检索上下文评判。"
    )
    data["meta"]["db_name"] = db_name
    data["summary"] = {
        "vector": _summarize(items, "vector", "V"),
        "graph": _summarize(items, "graph", "G"),
        "both": _summarize(items, "both", "VG"),
    }
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="单文献 RAG 真实生成 + 评测")
    p.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--ids", type=str, default="", help="逗号分隔，如 V1,G2")
    p.add_argument("--links", type=str, default="vector,graph,both")
    p.add_argument("--skip-judge", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    ids = [x.strip() for x in args.ids.split(",") if x.strip()] or None
    links = [x.strip() for x in args.links.split(",") if x.strip()]
    run_eval(
        input_path=args.input,
        output_path=args.output,
        ids=ids,
        links=links,
        skip_judge=args.skip_judge,
        dry_run=args.dry_run,
    )
    print(f"\nWrote {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
