from src.integrations.llm.embedding import Reranker
from src.services.rag.llm_filter import llm_extract_filter_cond
from src.services.graph.relation_labels import rel_label_zh
from src.utils.logging_config import setup_logger
from typing import Any

logger = setup_logger("server-common")

_SECTION_WEIGHT = {
    "experiment": 0.12,
    "result": 0.12,
    "method": 0.04,
    "intro": 0.02,
    "abstract": 0.0,
    "reference": 0.01,
    "title": 0.0,
}


def _is_sota_query(q: str) -> bool:
    q = q.lower()
    return any(
        k in q
        for k in ("sota", "最优", "最好", "state of the art", "benchmark", "顶会", "领先", "最新模型")
    )


def _query_needs_hyde(query: str) -> bool:
    q = (query or "").lower()
    return any(
        k in q
        for k in (
            "动机", "原理", "创新", "概述", "为什么", "整体流程", "架构",
            "motivation", "overview", "why", "innovation", "architecture",
        )
    )


def _strip_entity_suffix(name: str) -> str:
    s = (name or "").strip()
    for suffix in ("模型", "网络", "方法", "算法"):
        if s.endswith(suffix) and len(s) > len(suffix):
            s = s[: -len(suffix)].strip()
    return s


def _infer_task_domain(query: str, entities: list[str] | None, store=None, kb_id: str = "", user_id: str | int = 0) -> str | None:
    llm_td: str | None = None
    try:
        fj = llm_extract_filter_cond(query)
        llm_td = (fj.get("task_domain") or "").strip() or None
    except Exception as exc:
        logger.debug("task_domain extract failed: %s", exc)

    if store and kb_id and _is_sota_query(query):
        domains = store.list_task_domains(kb_id=kb_id, user_id=user_id, limit=20)
        if domains:
            if llm_td:
                llm_lower = llm_td.lower()
                for domain in domains:
                    d = (domain or "").strip().lower()
                    if d and (llm_lower in d or d in llm_lower):
                        return domain
            q = query.lower()
            for domain in domains:
                d = (domain or "").strip().lower()
                if d and (d in q or any(tok in d for tok in q.split() if len(tok) > 2)):
                    return domain
            return domains[0]

    if llm_td:
        return llm_td
    if entities:
        joined = " ".join(_strip_entity_suffix(e.strip()) for e in entities[:3] if e and e.strip())
        if joined:
            return joined
    return None


def _fetch_chunks_by_ids(chunk_ids: list[str]) -> list[dict]:
    if not chunk_ids:
        return []
    from src.models.base import SessionLocal
    from src.services.rag.indexing_pipeline import fetch_chunks_by_ids

    session = SessionLocal()
    try:
        rows = fetch_chunks_by_ids(session, chunk_ids[:30])
        return [
            {
                "chunk_id": r.chunk_id,
                "chunk_text": r.chunk_text,
                "page_num": r.page_num,
                "section_type": r.section_type,
                "paper_id": r.paper_id,
            }
            for r in rows
        ]
    finally:
        session.close()


def _node_display_name(node) -> str:
    """兼容 Paper(title/paper_id) 与 Model/Dataset 等(name) 节点。"""
    props = getattr(node, "_properties", None) or {}
    for key in ("name", "title", "paper_id"):
        val = props.get(key)
        if val:
            text = str(val).strip()
            if key == "title" and len(text) > 64:
                return text[:64] + "..."
            return text
    return "unknown"


def _node_label_type(node) -> str:
    labels = list(getattr(node, "labels", None) or [])
    return labels[0] if labels else "Entity"


def _node_graph_props(node) -> dict[str, Any]:
    """按节点类型统一领域字段，并提取图谱展示用元数据。"""
    props = getattr(node, "_properties", None) or {}
    label_type = _node_label_type(node)
    domain = ""
    if label_type in {"Paper", "Model"}:
        domain = str(props.get("task_domain") or "").strip()
    elif label_type == "Dataset":
        domain = str(props.get("task") or "").strip()
    elif label_type == "Metric":
        domain = str(props.get("applicable_task") or "").strip()

    year = props.get("year")
    if year is not None and year != "":
        try:
            year = int(year)
        except (TypeError, ValueError):
            year = None
    else:
        year = None

    return {
        "task_domain": domain,
        "description": str(props.get("description") or "").strip(),
        "innovation_summary": str(props.get("innovation_summary") or "").strip(),
        "year": year,
        "venue": str(props.get("venue") or "").strip(),
        "paper_id": str(props.get("paper_id") or "").strip(),
        "ccf_rank": str(props.get("ccf_rank") or "").strip(),
        "venue_type": str(props.get("type") or "").strip(),
    }


def _build_node_info(node, display_name: str) -> dict[str, Any]:
    return {
        "id": node.element_id,
        "name": display_name,
        "type": _node_label_type(node),
        **_node_graph_props(node),
    }


class Retriever:

    def __init__(self, config, dbm, model):
        self.config = config
        self.dbm = dbm
        self.model = model
        self.use_reranker = bool(getattr(config, "enable_reranker", True))
        self.reranker = None
        if self.use_reranker:
            try:
                self.reranker = Reranker(config)
            except Exception as exc:
                logger.warning("Reranker unavailable, disabled: %s", exc)
                self.use_reranker = False

    def retrieval(self, query, history, meta):

        refs = {"query": query, "history": history, "meta": meta}
        refs["model_name"] = self.config.model_name
        refs["entities"] = self.reco_entities(query, history, refs)
        refs["knowledge_base"] = self.query_knowledgebase(query, history, refs)
        refs["graph_base"] = self.query_graph(query, history, refs)

        return refs

    def construct_query(self, query, refs, meta):
        if not refs or len(refs) == 0:
            return query

        from src.integrations.llm.prompts import knowbase_qa_template
        from src.services.rag.retrieval_fusion import build_fused_external

        kb_res = refs.get("knowledge_base", {}).get("results", [])
        db_res = refs.get("graph_base", {}).get("results", {}) or {}
        intent = db_res.get("intent") or refs.get("graph_intent") or ""
        external = build_fused_external(
            kb_res,
            db_res,
            intent=intent,
            use_graph=bool(meta.get("use_graph")),
        )
        if external:
            query = knowbase_qa_template.format(external=external, query=query)
        return query

    def query_classification(self, query):
        raise NotImplementedError

    def _empty_graph_results(self) -> dict:
        return {
            "results": {
                "nodes": [],
                "edges": [],
                "chunks": [],
                "chain_summary": "",
                "sota_summary": "",
                "cite_summary": "",
                "intent": "",
            }
        }

    def _resolve_graph_kb(self, meta: dict) -> tuple[str, str | int]:
        db_name = meta.get("db_name") or ""
        kb_row = self.dbm.resolve_kb(db_name) if db_name else None
        kb_id = kb_row.kb_id if kb_row else self.dbm.get_default_public_kb_id()
        user_id = meta.get("user_id") or meta.get("owner_user_id") or 0
        return kb_id, user_id

    def _route_intent_by_entities(self, intent: str, entities: dict[str, list[str]]) -> str:
        if entities.get("Metric") and intent in {"General_Summary", "Model_Improve"}:
            return "Metric_Eval"
        if entities.get("Dataset") and intent in {"General_Summary", "Model_Improve"}:
            return "Dataset_Use"
        return intent

    def query_graph(self, query, history, refs):
        empty = self._empty_graph_results()
        if not refs["meta"].get("use_graph"):
            return empty
        if not self.config.enable_knowledge_graph or not self.dbm.graph_store:
            return empty

        meta = refs["meta"]
        kb_id, user_id = self._resolve_graph_kb(meta)
        store = self.dbm.graph_store

        from src.services.graph.graph_query_router import (
            classify_graph_intent,
            resolve_typed_entities,
            run_intent_graph_query,
        )

        typed_entities = refs.get("typed_entities") or []
        if not typed_entities:
            flat = refs.get("entities") or []
            typed_entities = [{"raw_name": e, "entity_type": "Model"} for e in flat if (e or "").strip()]

        entities = resolve_typed_entities(
            typed_entities,
            store,
            kb_id=kb_id,
            user_id=user_id,
        )

        flat_names = refs.get("entities") or []
        task_domain = _infer_task_domain(query, flat_names, store=store, kb_id=kb_id, user_id=user_id)

        intent = classify_graph_intent(query, self.model)
        intent = self._route_intent_by_entities(intent, entities)
        logger.debug("graph intent=%s entities=%s", intent, entities)

        results = run_intent_graph_query(
            store,
            query,
            intent,
            entities,
            kb_id=kb_id,
            user_id=user_id,
            task_domain=task_domain,
            fetch_chunks_fn=_fetch_chunks_by_ids,
        )

        if not results.get("nodes") and not results.get("edges") and not results.get("chunks"):
            if not results.get("chain_summary") and not results.get("sota_summary") and not results.get("cite_summary"):
                return empty

        refs["graph_intent"] = intent
        return {"results": results}

    def query_knowledgebase(self, query, history, refs):
        """查询知识库"""

        kb_res = []
        final_res = []

        db_name = refs["meta"].get("db_name")
        if not db_name or not self.config.enable_knowledge_base:
            return {
                "results": final_res,
                "all_results": kb_res,
                "rw_query": query,
                "message": "Knowledge base is disabled",
            }

        rw_query = self.rewrite_query(query, history, refs)
        refs["rewritten_query"] = rw_query

        kb_row = self.dbm.resolve_kb(db_name)
        if not kb_row:
            return {
                "results": final_res,
                "all_results": kb_res,
                "rw_query": rw_query,
                "message": f"Unknown knowledge base: {db_name}",
            }

        logger.debug(f"{refs['meta']=}")

        meta = refs["meta"]
        max_query_count = meta.get("maxQueryCount", 10)
        rerank_threshold = meta.get("rerankThreshold", 0.1)
        distance_threshold = meta.get("distanceThreshold", 0)
        top_k = meta.get("topK", 5)
        user_id = meta.get("user_id") or meta.get("owner_user_id") or 0

        filter_json = llm_extract_filter_cond(query) if meta.get("use_llm_filter") else {}
        for key in ("keywords", "task_domain", "section_type", "block_type"):
            filter_json.pop(key, None)

        all_kb_res = self.dbm.search_knowledge_base(
            rw_query,
            db_name,
            user_id=user_id,
            filter_json=filter_json,
            limit=max_query_count,
        )
        for r in all_kb_res:
            entity = r.get("entity") or {}
            file_id = entity.get("file_id")
            paper_id = entity.get("paper_id")
            r["file"] = None
            if file_id:
                r["file"] = self.dbm.id2file(kb_row.kb_id, file_id)
            if not r.get("file") and paper_id:
                r["file"] = self.dbm.id2paper(paper_id)
            if not r.get("file") and file_id:
                r["file"] = self.dbm.id2paper(file_id)

        if meta.get("mode") == "search":
            kb_res = all_kb_res
        else:
            kb_res = [r for r in all_kb_res if r["distance"] >= distance_threshold]

        if self.use_reranker and self.reranker:
            for r in kb_res:
                r["rerank_score"] = self.reranker.compute_score([rw_query, r["entity"]["text"]], normalize=True)[0]
            kb_res.sort(key=lambda x: x["rerank_score"], reverse=True)
            kb_res = [_res for _res in kb_res if _res["rerank_score"] > rerank_threshold]

        for r in kb_res:
            section = ((r.get("entity") or {}).get("section_type") or "").lower()
            boost = _SECTION_WEIGHT.get(section, 0.0)
            base = r.get("rerank_score", r.get("distance", 0))
            r["_sort_score"] = base + boost
        kb_res.sort(key=lambda x: x["_sort_score"], reverse=True)

        kb_res = kb_res[:top_k]

        return {"results": kb_res, "all_results": all_kb_res, "rw_query": rw_query, "filter_json": filter_json}

    def rewrite_query(self, query, history, refs):
        """重写查询；抽象/动机类默认 HyDE，其余保持原问句或轻量改写。"""
        rewrite_query_span = refs["meta"].get("rewriteQuery")
        if rewrite_query_span is None or rewrite_query_span == "":
            use_hyde = _query_needs_hyde(query)
            use_rewrite = use_hyde
        elif rewrite_query_span == "off":
            use_hyde = False
            use_rewrite = False
        elif rewrite_query_span == "hyde":
            use_hyde = True
            use_rewrite = True
        else:
            use_hyde = False
            use_rewrite = True

        if not use_rewrite:
            return query

        from src.integrations.llm.prompts import rewritten_query_prompt_template

        history_query = [entry["content"] for entry in history if entry["role"] == "user"] if history else ""
        rewritten_query_prompt = rewritten_query_prompt_template.format(history=history_query, query=query)
        rewritten_query = self.model.predict(rewritten_query_prompt).content

        if use_hyde:
            hy_doc = self.model.predict(rewritten_query).content
            rewritten_query = f"{rewritten_query} {hy_doc}"

        return rewritten_query

    def reco_entities(self, query, history, refs):
        """识别句子中的实体/关键词（供图谱检索），并写入 refs['typed_entities']。"""
        query = refs.get("rewritten_query", query)

        entities: list[str] = []
        refs["typed_entities"] = []
        if refs["meta"].get("use_graph"):
            from src.integrations.llm.prompts import graph_typed_entities_prompt_template
            from src.services.graph.graph_query_router import (
                classify_graph_intent,
                parse_typed_entities_raw,
                resolve_typed_entities,
                run_intent_graph_query,
                sanitize_entity_raw,
            )

            prompt = graph_typed_entities_prompt_template.format(text=query)
            raw = self.model.predict(prompt).content
            typed = []
            for item in parse_typed_entities_raw(raw):
                clean = sanitize_entity_raw(item.get("raw_name") or "")
                if clean:
                    typed.append({**item, "raw_name": clean})
            refs["typed_entities"] = typed
            entities = [t["raw_name"] for t in typed if t.get("raw_name")]

        return entities

    def _extract_relationship_info(self, relationship, source_name, target_name):
        rel_id = relationship.element_id
        nodes = relationship.nodes
        if len(nodes) != 2:
            return None, None

        source, target = nodes
        source_id = source.element_id
        target_id = target.element_id

        relationship_type = relationship._properties.get("type", "unknown")
        if relationship_type == "unknown":
            relationship_type = relationship.type
        rel_type_raw = str(relationship_type or "RELATION")
        relationship_type = rel_label_zh(relationship_type)

        edge_info = {
            "id": rel_id,
            "type": relationship_type,
            "rel_type": rel_type_raw,
            "source_id": source_id,
            "target_id": target_id,
            "source_name": source_name,
            "target_name": target_name,
        }

        node_info = [
            _build_node_info(source, source_name),
            _build_node_info(target, target_name),
        ]

        return node_info, edge_info

    def format_general_results(self, results):
        formatted_results = {"nodes": [], "edges": []}

        for item in results:
            relationship = item[1] if len(item) > 1 else None
            if relationship is None:
                solo = item[0]
                if solo is not None and hasattr(solo, "element_id"):
                    node = _build_node_info(solo, _node_display_name(solo))
                    if node["id"] not in [n["id"] for n in formatted_results["nodes"]]:
                        formatted_results["nodes"].append(node)
                continue

            source_name = _node_display_name(item[0])
            target_name = _node_display_name(item[2]) if len(item) > 2 else "unknown"

            node_info, edge_info = self._extract_relationship_info(relationship, source_name, target_name)
            if node_info is None or edge_info is None:
                continue

            for node in node_info:
                if node["id"] not in [n["id"] for n in formatted_results["nodes"]]:
                    formatted_results["nodes"].append(node)

            formatted_results["edges"].append(edge_info)

        return formatted_results

    def format_query_results(self, results):
        formatted_results = {"nodes": [], "edges": []}
        node_dict = {}

        for item in results:
            if not isinstance(item[1], list) or not item[1]:
                continue

            relationship = item[1][0]
            source_name = item[0]
            target_name = item[2] if len(item) > 2 else "unknown"

            node_info, edge_info = self._extract_relationship_info(relationship, source_name, target_name)
            if node_info is None or edge_info is None:
                continue

            node_dict.update({node["id"]: node for node in node_info})
            formatted_results["edges"].append(edge_info)

        formatted_results["nodes"] = list(node_dict.values())

        return formatted_results

    def __call__(self, query, history, meta):
        refs = self.retrieval(query, history, meta)
        query = self.construct_query(query, refs, meta)
        return query, refs
