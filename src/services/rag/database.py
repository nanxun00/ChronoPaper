"""知识库管理门面（底层 MySQL + 单集合 Milvus）。"""
from __future__ import annotations

from src.services.rag.knowledge_base_service import KnowledgeBaseService


class DataBaseManager(KnowledgeBaseService):
    """兼容旧 startup.dbm 调用入口。"""

    def __init__(self, config=None) -> None:
        super().__init__(config)
        self.data = {"databases": [], "graph": {}}
        self._update_database()
        if self.config.enable_knowledge_base:
            self.ensure_default_knowledge_base()

    def _update_database(self) -> None:
        self._refresh_maps()
        by_kb = self._maps.get("by_kb_id") or {}
        by_meta = self._maps.get("by_metaname") or {}
        self.id2db = by_kb
        self.name2db = self._maps.get("by_name") or {}
        self.metaname2db = by_meta

    def get_databases(self):
        result = super().get_databases()
        self._update_database()
        return result

    def create_database(self, *args, **kwargs):
        result = super().create_database(*args, **kwargs)
        self._update_database()
        return result

    def delete_database(self, db_id):
        result = super().delete_database(db_id)
        self._update_database()
        return result

    def resolve_kb_record(self, db_name: str):
        return self.resolve_kb(db_name)
