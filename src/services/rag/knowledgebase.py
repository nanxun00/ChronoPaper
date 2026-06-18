"""全局 paper_text_chunk 向量读写（无长文本）。"""
from __future__ import annotations

from typing import Any

from pymilvus import MilvusClient, MilvusException

from src.integrations.llm.embedding import get_embedding_model
from src.services.rag.owner_scope import milvus_owner_user_id
from src.services.rag.milvus_collection import PAPER_TEXT_CHUNK, ensure_paper_text_chunk, get_embed_dimension
from src.utils.logging_config import setup_logger

logger = setup_logger("KnowledgeBase")


class KnowledgeBase:
    COLLECTION = PAPER_TEXT_CHUNK

    def __init__(self, config=None, embed_model=None) -> None:
        self.config = config or {}
        if embed_model is None:
            embed_model = get_embedding_model(self.config)
        assert embed_model, "embed_model=None"
        self.embed_model = embed_model
        self.dimension = get_embed_dimension(self.config)
        self.client: MilvusClient | None = None
        if not self.connect_to_milvus():
            raise ConnectionError("Failed to connect to Milvus")

    def connect_to_milvus(self) -> bool:
        try:
            uri = self.config.milvus.get("uri", "http://localhost:19530")
            token = self.config.milvus.get("token", "")
            db_name = (self.config.milvus.get("db_name") or "chronopaper").strip()

            root = MilvusClient(uri=uri, token=token)
            if db_name:
                existing = set(root.list_databases())
                if db_name not in existing:
                    root.create_database(db_name)
                    logger.info("Created Milvus database %r", db_name)

            self.client = MilvusClient(uri=uri, token=token, db_name=db_name or None)
            ensure_paper_text_chunk(self.client, self.dimension)
            self.client.load_collection(self.COLLECTION)
            logger.info("Milvus ready collection=%s dim=%s db=%s", self.COLLECTION, self.dimension, db_name)
            return True
        except MilvusException as exc:
            logger.error("Failed to connect to Milvus: %s", exc)
            return False

    def ensure_collection(self, _collection_name: str, dimension: int | None = None) -> bool:
        """兼容旧接口：统一校验全局集合。"""
        dim = dimension or self.dimension
        ensure_paper_text_chunk(self.client, dim)
        return False

    def add_collection(self, _collection_name, dimension=None):
        """兼容旧接口：不再按知识库创建独立 collection。"""
        ensure_paper_text_chunk(self.client, dimension or self.dimension)

    def upsert_vectors(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        texts = [r["chunk_text"] for r in rows]
        vectors = self.embed_model.encode(texts)
        if vectors and len(vectors[0]) != self.dimension:
            raise ValueError(
                f"Embedding dim mismatch: got {len(vectors[0])}, expected {self.dimension}"
            )
        payload = []
        for i, row in enumerate(rows):
            keywords = row.get("keywords") or []
            if isinstance(keywords, str):
                import json

                try:
                    keywords = json.loads(keywords)
                except json.JSONDecodeError:
                    keywords = []
            payload.append(
                {
                    "chunk_id": row["chunk_id"],
                    "vec": vectors[i],
                    "paper_id": row.get("paper_id") or "",
                    "doc_id": row.get("doc_id") or "",
                    "kb_id": row["kb_id"],
                    "resource_type": row.get("resource_type") or "public",
                    "owner_user_id": milvus_owner_user_id(row.get("owner_user_id")),
                    "year": int(row.get("year") or 0),
                    "ccf_rank": row.get("ccf_rank") or "None",
                    "section_type": row.get("section_type") or "text",
                    "block_type": row.get("block_type") or "text",
                    "task_domain": row.get("task_domain") or "",
                    "keywords": keywords if isinstance(keywords, list) else [],
                    "text_hash": row.get("text_hash") or "",
                }
            )
        self.client.upsert(collection_name=self.COLLECTION, data=payload)

    def delete_by_chunk_ids(self, chunk_ids: list[str]) -> None:
        if not chunk_ids:
            return
        quoted = ", ".join(f'"{cid}"' for cid in chunk_ids)
        self.client.delete(collection_name=self.COLLECTION, filter=f"chunk_id in [{quoted}]")

    def delete_by_kb_id(self, kb_id: str) -> None:
        self.client.delete(collection_name=self.COLLECTION, filter=f"kb_id == '{kb_id}'")

    def search(
        self,
        query: str,
        *,
        filter_expr: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        query_vectors = self.embed_model.encode_queries([query])
        res = self.client.search(
            collection_name=self.COLLECTION,
            data=[query_vectors[0]],
            filter=filter_expr,
            limit=limit,
            output_fields=["chunk_id", "paper_id", "doc_id", "kb_id"],
        )
        return res[0] if res else []

    def get_collection_info(self, _collection_name: str | None = None, dimension: int | None = None):
        ensure_paper_text_chunk(self.client, dimension or self.dimension)
        stats = self.client.get_collection_stats(self.COLLECTION)
        return {
            "collection_name": self.COLLECTION,
            "row_count": int(stats.get("row_count", 0)),
        }

    def get_collection_names(self):
        return self.client.list_collections()

    def has_collection(self, collection_name: str) -> bool:
        if collection_name == self.COLLECTION:
            return self.client.has_collection(self.COLLECTION)
        return False
