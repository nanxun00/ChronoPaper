from src.integrations.llm.embedding import Reranker
from src.services.rag.llm_filter import llm_extract_filter_cond
from src.services.graph.relation_labels import rel_label_zh
from src.utils.logging_config import setup_logger
from typing import Any

logger = setup_logger("server-common")


def _is_sota_query(q: str) -> bool:
    q = q.lower()
    return any(
        k in q
        for k in ("sota", "最优", "最好", "state of the art", "benchmark", "顶会", "领先", "最新模型")
    )


def _is_citation_query(q: str) -> bool:
    q = q.lower()
    return any(k in q for k in ("引用", "cite", "citation", "参考文献", "被引", "引用关系", "引用网络"))


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

        if self.config.enable_reranker:
            self.reranker = Reranker(config)

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

        external_parts = []

        kb_res = refs.get("knowledge_base", {}).get("results", [])
        if kb_res:
            kb_text = "\n".join(f"{r['id']}: {r['entity']['text']}" for r in kb_res)
            external_parts.extend(["知识库信息:", kb_text])

        db_res = refs.get("graph_base", {}).get("results", {})
        graph_chunks = db_res.get("chunks") or []
        if graph_chunks:
            chunk_text = "\n".join(
                f"{c['chunk_id']}: {c.get('chunk_text', '')[:800]}" for c in graph_chunks[:8]
            )
            external_parts.extend(["图谱原文证据:", chunk_text])

        if db_res.get("nodes") and len(db_res["nodes"]) > 0:
            db_text = "\n".join(
                [
                    f"{edge.get('source_name')}和{edge.get('target_name')}的关系是{edge.get('type')}"
                    for edge in db_res.get("edges", [])
                ]
            )
            if db_text:
                external_parts.extend(["图数据库关系:", db_text])

        chain = db_res.get("chain_summary")
        if chain:
            external_parts.extend(["模型时序链:", chain])

        sota_summary = db_res.get("sota_summary")
        if sota_summary:
            external_parts.extend(["领域SOTA:", sota_summary])

        cite_summary = db_res.get("cite_summary")
        if cite_summary:
            external_parts.extend(["引用脉络:", cite_summary])

        from src.integrations.llm.prompts import knowbase_qa_template
        if external_parts and len(external_parts) > 0:
            external = "\n\n".join(external_parts)
            query = knowbase_qa_template.format(external=external, query=query)

        return query

    def query_classification(self, query):
        raise NotImplementedError

    def query_graph(self, query, history, refs):
        empty = {
            "results": {
                "nodes": [],
                "edges": [],
                "chunks": [],
                "chain_summary": "",
                "sota_summary": "",
                "cite_summary": "",
            }
        }
        if not refs["meta"].get("use_graph"):
            return empty
        if not self.config.enable_knowledge_graph or not self.dbm.graph_store:
            return empty

        meta = refs["meta"]
        db_name = meta.get("db_name") or ""
        kb_row = self.dbm.resolve_kb(db_name) if db_name else None
        if not kb_row:
            kb_id = self.dbm.get_default_public_kb_id()
        else:
            kb_id = kb_row.kb_id
        user_id = meta.get("user_id") or meta.get("owner_user_id") or 0

        from src.services.graph.entity_normalize import normalize_entity

        entities = refs.get("entities") or []
        model_names: list[str] = []
        for entity in entities:
            name = _strip_entity_suffix((entity or "").strip())
            if not name:
                continue
            std = normalize_entity(name, "Model")
            if std:
                model_names.append(std)

        store = self.dbm.graph_store
        if not model_names:
            for entity in entities:
                name = _strip_entity_suffix((entity or "").strip())
                if not name:
                    continue
                found = store.find_models_by_keyword(name, kb_id=kb_id, user_id=user_id, limit=3)
                model_names.extend(found)
        model_names = list(dict.fromkeys(model_names))[:5]

        graph_data: dict = {"models": [], "edges": [], "chunk_ids": []}
        if model_names:
            graph_data = store.query_temporal_chain(
                model_names,
                kb_id=kb_id,
                user_id=user_id,
                limit=20,
            )

        paper_ids: list[str] = []
        for m in graph_data.get("models") or []:
            for pid in m.get("paper_ids") or []:
                if pid and pid not in paper_ids:
                    paper_ids.append(pid)

        task_domain = _infer_task_domain(query, entities, store=store, kb_id=kb_id, user_id=user_id)
        sota_data: dict = {"models": [], "chunk_ids": []}
        if task_domain and (_is_sota_query(query) or not model_names):
            sota_data = store.query_sota_models(
                task_domain=task_domain,
                kb_id=kb_id,
                user_id=user_id,
                limit=10,
            )
            for row in sota_data.get("models") or []:
                pid = row.get("paper_id")
                if pid and pid not in paper_ids:
                    paper_ids.append(pid)

        cite_data: dict = {"papers": [], "edges": [], "chunk_ids": []}
        if paper_ids or _is_citation_query(query):
            cite_data = store.query_citation_network(
                paper_ids,
                kb_id=kb_id,
                user_id=user_id,
                hops=2,
                limit=30,
            )

        if (
            not graph_data.get("models")
            and not sota_data.get("models")
            and not cite_data.get("edges")
            and not cite_data.get("papers")
        ):
            return empty

        chunk_ids: list[str] = []
        for src in (graph_data, sota_data, cite_data):
            for cid in src.get("chunk_ids") or []:
                if cid not in chunk_ids:
                    chunk_ids.append(cid)
        chunks = _fetch_chunks_by_ids(chunk_ids)

        nodes: list[dict] = []
        edges: list[dict] = []
        seen_nodes: set[str] = set()

        def _add_node(node_id: str, name: str, ntype: str):
            if not node_id or node_id in seen_nodes:
                return
            seen_nodes.add(node_id)
            nodes.append({"id": node_id, "name": name, "type": ntype})

        chain_parts = []
        for m in graph_data.get("models") or []:
            name = m.get("name")
            if not name:
                continue
            _add_node(name, name, "Model")
            year = m.get("birth_year")
            if year:
                chain_parts.append(f"{name}({year})")
        for e in graph_data.get("edges") or []:
            src, tgt = e.get("source"), e.get("target")
            if src:
                _add_node(src, src, "Model")
            if tgt:
                _add_node(tgt, tgt, "Model")
            edges.append(
                {
                    "id": f"{src}-{tgt}",
                    "type": rel_label_zh(e.get("rel_type") or "IMPROVE_FROM"),
                    "source_id": src,
                    "target_id": tgt,
                    "source_name": src,
                    "target_name": tgt,
                }
            )

        sota_lines: list[str] = []
        for row in sota_data.get("models") or []:
            model = row.get("model")
            if not model:
                continue
            _add_node(model, model, "Model")
            ds = ", ".join(d for d in (row.get("datasets") or []) if d)
            metrics = ", ".join(x for x in (row.get("metrics") or []) if x)
            paper_title = row.get("paper_title") or row.get("paper_id") or ""
            year = row.get("year") or row.get("paper_year")
            sota_lines.append(
                f"{model}({year or '?'}) | 论文:{paper_title} | 数据集:{ds or '-'} | 指标:{metrics or '-'}"
            )
            pid = row.get("paper_id")
            if pid:
                _add_node(pid, paper_title or pid, "Paper")

        for p in cite_data.get("papers") or []:
            pid = p.get("paper_id")
            pname = p.get("name") or p.get("title") or pid
            if pid:
                _add_node(pid, pname, "Paper")

        cite_lines: list[str] = []
        for e in cite_data.get("edges") or []:
            src = e.get("source_name") or e.get("source")
            tgt = e.get("target_name") or e.get("target")
            cite_lines.append(f"{src} → 引用 → {tgt}")
            edges.append(
                {
                    "id": f"{e.get('source')}-{e.get('target')}-cite",
                    "type": rel_label_zh("CITE"),
                    "source_id": e.get("source"),
                    "target_id": e.get("target"),
                    "source_name": src,
                    "target_name": tgt,
                }
            )

        chain_summary = " → ".join(chain_parts) if chain_parts else ""
        sota_summary = "\n".join(sota_lines) if sota_lines else ""
        cite_summary = "\n".join(cite_lines[:15]) if cite_lines else ""

        return {
            "results": {
                "nodes": nodes,
                "edges": edges,
                "chunks": chunks,
                "chain_summary": chain_summary,
                "sota_summary": sota_summary,
                "cite_summary": cite_summary,
            }
        }

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

        if self.config.enable_reranker:
            for r in kb_res:
                r["rerank_score"] = self.reranker.compute_score([rw_query, r["entity"]["text"]], normalize=True)[0]
            kb_res.sort(key=lambda x: x["rerank_score"], reverse=True)
            kb_res = [_res for _res in kb_res if _res["rerank_score"] > rerank_threshold]

        kb_res = kb_res[:top_k]

        return {"results": kb_res, "all_results": all_kb_res, "rw_query": rw_query, "filter_json": filter_json}

    def rewrite_query(self, query, history, refs):
        """重写查询"""
        rewrite_query_span = refs["meta"].get("rewriteQuery", "off")
        if rewrite_query_span == "off":
            rewritten_query = query
        else:
            from src.integrations.llm.prompts import rewritten_query_prompt_template

            history_query = [entry["content"] for entry in history if entry["role"] == "user"] if history else ""
            rewritten_query_prompt = rewritten_query_prompt_template.format(history=history_query, query=query)
            rewritten_query = self.model.predict(rewritten_query_prompt).content

        if rewrite_query_span == "hyde":
            hy_doc = self.model.predict(rewritten_query).content
            rewritten_query = f"{rewritten_query} {hy_doc}"

        return rewritten_query

    def reco_entities(self, query, history, refs):
        """识别句子中的实体/关键词（供图谱检索）。"""
        query = refs.get("rewritten_query", query)

        entities = []
        if refs["meta"].get("use_graph"):
            from src.integrations.llm.prompts import keywords_prompt_template

            prompt = keywords_prompt_template.format(text=query)
            raw = self.model.predict(prompt).content
            entities = [e.strip() for e in raw.split("<->") if e.strip()]

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
            relationship = item[1]
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
