"""知识库管理（MySQL knowledge_base 表，底层单集合 paper_text_chunk）。"""
from __future__ import annotations

import os
import time
from typing import Any

from sqlalchemy.orm import Session

from src.config import EMBED_MODEL_INFO
from src.integrations.llm.embedding import get_embedding_model
from src.models.base import SessionLocal
from src.models.rag import KnowledgeBaseFile, KnowledgeBaseRecord, TextChunk
from src.services.rag.indexing_pipeline import fetch_chunks_by_ids, index_chunk_rows, soft_delete_kb_chunks
from src.services.rag.knowledgebase import KnowledgeBase
from src.services.rag.filters import build_milvus_filter
from src.services.rag.milvus_collection import get_embed_dimension
from src.services.rag.owner_scope import milvus_owner_user_id
from src.settings import get_settings
from src.utils import hashstr, setup_logger
from src.utils.snowflake import next_snowflake_id

logger = setup_logger("KnowledgeBaseService")

DEFAULT_KB_NAME = "ChronoPaper 公共文献库"


class KnowledgeBaseService:
    def __init__(self, config=None) -> None:
        self.config = config
        settings = get_settings()
        self.embed_model = get_embedding_model(config)
        self.knowledge_base = KnowledgeBase(config, self.embed_model) if config.enable_knowledge_base else None
        self.graph_base = None
        if config.enable_knowledge_base and config.enable_knowledge_graph:
            try:
                from src.services.rag.graphbase import GraphDatabase

                self.graph_base = GraphDatabase(config, self.embed_model)
                self.graph_base.start()
            except Exception as exc:
                logger.warning("Knowledge graph disabled due to init error: %s", exc)
                self.graph_base = None
        self._maps: dict[str, Any] = {}
        self._refresh_maps()

    def _session(self) -> Session:
        return SessionLocal()

    def _refresh_maps(self) -> None:
        session = self._session()
        try:
            rows = session.query(KnowledgeBaseRecord).order_by(KnowledgeBaseRecord.created_at.asc()).all()
            self._maps = {
                "by_kb_id": {r.kb_id: r for r in rows},
                "by_metaname": {r.metaname: r for r in rows},
                "by_name": {r.name: r for r in rows},
            }
        finally:
            session.close()

    def ensure_default_knowledge_base(self) -> KnowledgeBaseRecord:
        session = self._session()
        try:
            row = session.query(KnowledgeBaseRecord).filter(KnowledgeBaseRecord.is_system == 1).first()
            if row:
                return row
            kb_id = next_snowflake_id()
            metaname = KnowledgeBaseRecord.metaname_for(kb_id)
            dim = get_embed_dimension(self.config)
            row = KnowledgeBaseRecord(
                kb_id=kb_id,
                name=DEFAULT_KB_NAME,
                description="系统默认公共文献向量库",
                db_type="knowledge",
                metaname=metaname,
                embed_model=self.config.embed_model,
                dimension=dim,
                owner_user_id="",
                is_system=1,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            self._refresh_maps()
            return row
        finally:
            session.close()

    def resolve_kb(self, db_name: str | None) -> KnowledgeBaseRecord | None:
        if not db_name:
            return None
        self._refresh_maps()
        return (
            self._maps["by_metaname"].get(db_name)
            or self._maps["by_kb_id"].get(db_name)
            or self._maps["by_name"].get(db_name)
        )

    def get_default_public_kb_id(self) -> str:
        return self.ensure_default_knowledge_base().kb_id

    def get_databases(self) -> dict:
        assert self.config.enable_knowledge_base
        session = self._session()
        try:
            rows = session.query(KnowledgeBaseRecord).order_by(KnowledgeBaseRecord.created_at.desc()).all()
            if not rows:
                self.ensure_default_knowledge_base()
                rows = session.query(KnowledgeBaseRecord).all()
            out = []
            for row in rows:
                count = (
                    session.query(TextChunk)
                    .filter(TextChunk.kb_id == row.kb_id, TextChunk.is_deleted == 0)
                    .count()
                )
                files = (
                    session.query(KnowledgeBaseFile)
                    .filter(KnowledgeBaseFile.kb_id == row.kb_id)
                    .order_by(KnowledgeBaseFile.created_at.desc())
                    .all()
                )
                item = row.to_dict(row_count=count)
                item["files"] = [
                    {
                        "file_id": f.file_id,
                        "filename": f.filename,
                        "path": f.path,
                        "type": f.file_type,
                        "status": f.index_status,
                        "created_at": f.created_at.timestamp() if f.created_at else time.time(),
                    }
                    for f in files
                ]
                out.append(item)
            return {"databases": out}
        finally:
            session.close()

    def create_database(self, database_name, description, db_type, dimension):
        dim = dimension or get_embed_dimension(self.config)
        session = self._session()
        try:
            kb_id = next_snowflake_id()
            metaname = KnowledgeBaseRecord.metaname_for(kb_id)
            row = KnowledgeBaseRecord(
                kb_id=kb_id,
                name=database_name,
                description=description or "",
                db_type=db_type or "knowledge",
                metaname=metaname,
                embed_model=self.config.embed_model,
                dimension=dim,
            )
            session.add(row)
            session.commit()
            if self.knowledge_base:
                self.knowledge_base.ensure_collection(metaname, dim)
            self._refresh_maps()
            return self.get_databases()
        finally:
            session.close()

    def delete_database(self, db_id):
        session = self._session()
        try:
            row = session.query(KnowledgeBaseRecord).filter(KnowledgeBaseRecord.kb_id == db_id).first()
            if not row:
                return {"message": "database not found"}, 404
            if row.is_system:
                return {"message": "系统默认知识库不可删除"}, 400
            if self.knowledge_base:
                soft_delete_kb_chunks(session, self.knowledge_base, row.kb_id)
            session.query(KnowledgeBaseFile).filter(KnowledgeBaseFile.kb_id == row.kb_id).delete()
            session.delete(row)
            session.commit()
            self._refresh_maps()
            return {"message": "删除成功"}
        finally:
            session.close()

    def get_database_info(self, db_id):
        session = self._session()
        try:
            row = session.query(KnowledgeBaseRecord).filter(KnowledgeBaseRecord.kb_id == db_id).first()
            if not row:
                return None
            count = (
                session.query(TextChunk)
                .filter(TextChunk.kb_id == row.kb_id, TextChunk.is_deleted == 0)
                .count()
            )
            return row.to_dict(row_count=count, metadata=self.knowledge_base.get_collection_info() if self.knowledge_base else {})
        finally:
            session.close()

    def add_files(self, db_id, files, params=None):
        session = self._session()
        try:
            row = session.query(KnowledgeBaseRecord).filter(KnowledgeBaseRecord.kb_id == db_id).first()
            if not row:
                return {"message": "database not found", "status": "failed"}
            if row.embed_model != self.config.embed_model:
                return {
                    "message": f"Embed model not match, cur: {self.config.embed_model}",
                    "status": "failed",
                }
            from src.workers.index_tasks import index_kb_document_task

            queued = []
            for file in files:
                file_id = "file_" + hashstr(file + str(time.time()))
                doc_id = next_snowflake_id()
                kb_file = KnowledgeBaseFile(
                    file_id=file_id,
                    kb_id=row.kb_id,
                    doc_id=doc_id,
                    filename=os.path.basename(file),
                    path=file,
                    file_type=file.split(".")[-1].lower(),
                    status="waiting",
                    parse_status="pending",
                    index_status="queued",
                )
                session.add(kb_file)
                session.commit()
                index_kb_document_task.delay(row.kb_id, doc_id, file, file_id)
                queued.append(file_id)
            return {"message": "已提交 MinerU 解析与向量入库任务", "status": "success", "file_ids": queued}
        finally:
            session.close()

    def delete_file(self, db_id, file_id):
        session = self._session()
        try:
            kb_file = (
                session.query(KnowledgeBaseFile)
                .filter(KnowledgeBaseFile.kb_id == db_id, KnowledgeBaseFile.file_id == file_id)
                .first()
            )
            if not kb_file:
                return
            chunk_rows = (
                session.query(TextChunk.chunk_id)
                .filter(TextChunk.kb_id == db_id, TextChunk.doc_id == kb_file.doc_id, TextChunk.is_deleted == 0)
                .all()
            )
            chunk_ids = [c[0] for c in chunk_rows]
            session.query(TextChunk).filter(TextChunk.doc_id == kb_file.doc_id).update({"is_deleted": 1})
            session.delete(kb_file)
            session.commit()
            if self.knowledge_base and chunk_ids:
                self.knowledge_base.delete_by_chunk_ids(chunk_ids)
        finally:
            session.close()

    def get_file_info(self, db_id, file_id):
        session = self._session()
        try:
            kb_file = (
                session.query(KnowledgeBaseFile)
                .filter(KnowledgeBaseFile.kb_id == db_id, KnowledgeBaseFile.file_id == file_id)
                .first()
            )
            if not kb_file:
                return {"message": "file not found"}, 404
            lines = (
                session.query(TextChunk)
                .filter(TextChunk.kb_id == db_id, TextChunk.doc_id == kb_file.doc_id, TextChunk.is_deleted == 0)
                .limit(500)
                .all()
            )
            return {
                "lines": [
                    {
                        "id": line.chunk_id,
                        "text": line.chunk_text,
                        "file_id": file_id,
                        "hash": line.text_hash,
                    }
                    for line in lines
                ]
            }
        finally:
            session.close()

    def get_graph(self):
        if self.config.enable_knowledge_graph and self.graph_base:
            return {"graph": self.graph_base.get_database_info("neo4j")}
        return {"message": "Graph base not enabled", "graph": {}}

    def fetch_chunks_for_hits(self, chunk_ids: list[str]) -> dict[str, TextChunk]:
        session = self._session()
        try:
            rows = fetch_chunks_by_ids(session, chunk_ids)
            return {r.chunk_id: r for r in rows}
        finally:
            session.close()

    @staticmethod
    def _milvus_hit_score(hit: dict) -> float:
        raw = float(hit.get("distance", 0))
        return max(0.0, 1.0 - raw)

    def search_knowledge_base(
        self,
        query: str,
        db_name: str,
        *,
        user_id: int | str = 0,
        filter_json: dict | None = None,
        limit: int = 10,
    ) -> list[dict]:
        if not self.knowledge_base:
            return []
        kb_row = self.resolve_kb(db_name)
        if not kb_row:
            logger.warning("Unknown knowledge base: %s", db_name)
            return []

        filter_expr = build_milvus_filter(
            filter_json,
            kb_id=kb_row.kb_id,
            user_id=milvus_owner_user_id(user_id),
        )
        hits = self.knowledge_base.search(query, filter_expr=filter_expr, limit=limit)
        chunk_ids: list[str] = []
        for hit in hits:
            entity = hit.get("entity") or {}
            cid = entity.get("chunk_id") or hit.get("id")
            if cid:
                chunk_ids.append(str(cid))

        chunk_map = self.fetch_chunks_for_hits(chunk_ids)
        results: list[dict] = []
        for hit in hits:
            entity = hit.get("entity") or {}
            chunk_id = str(entity.get("chunk_id") or hit.get("id") or "")
            chunk = chunk_map.get(chunk_id)
            if not chunk:
                continue
            file_id = chunk.doc_id or chunk.paper_id or ""
            results.append(
                {
                    "id": chunk_id,
                    "distance": self._milvus_hit_score(hit),
                    "entity": {
                        "text": chunk.chunk_text,
                        "file_id": file_id,
                        "chunk_id": chunk_id,
                        "paper_id": chunk.paper_id or "",
                        "doc_id": chunk.doc_id or "",
                        "page_num": chunk.page_num,
                        "bbox": chunk.bbox,
                        "section_type": chunk.section_type,
                        "block_type": chunk.block_type,
                        "task_domain": chunk.task_domain,
                    },
                }
            )
        return results

    def id2file(self, kb_id: str, file_id: str):
        session = self._session()
        try:
            from sqlalchemy import or_

            row = (
                session.query(KnowledgeBaseFile)
                .filter(
                    KnowledgeBaseFile.kb_id == kb_id,
                    or_(
                        KnowledgeBaseFile.file_id == file_id,
                        KnowledgeBaseFile.doc_id == file_id,
                    ),
                )
                .first()
            )
            if not row:
                return None
            return {
                "file_id": row.file_id,
                "filename": row.filename,
                "path": row.path,
                "type": row.file_type,
                "status": row.index_status,
            }
        finally:
            session.close()
