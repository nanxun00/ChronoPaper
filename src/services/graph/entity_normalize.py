"""实体名称归一化（entity_alias 表 + 内存缓存）。"""
from __future__ import annotations

import re
import threading

from src.models.base import SessionLocal
from src.models.rag import EntityAlias
from src.utils.snowflake import next_snowflake_id

_ENTITY_TYPES = frozenset({"Model", "Dataset", "Metric", "Author", "Venue", "Paper"})


def clean_entity_name(raw_name: str) -> str:
    """去除空格、横杠、小数点并转小写。"""
    s = (raw_name or "").strip().lower()
    return re.sub(r"[\s\-\.]+", "", s)


class EntityAliasCache:
    _instance: EntityAliasCache | None = None
    _init_lock = threading.Lock()

    def __init__(self) -> None:
        self._alias_to_std: dict[str, str] = {}
        self._loaded = False
        self._lock = threading.Lock()

    @classmethod
    def get(cls) -> EntityAliasCache:
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def reload(self) -> None:
        session = SessionLocal()
        try:
            rows = session.query(EntityAlias).all()
            mapping: dict[str, str] = {}
            for row in rows:
                mapping[row.raw_alias] = row.std_name
                cleaned = clean_entity_name(row.raw_alias)
                if cleaned:
                    mapping.setdefault(cleaned, row.std_name)
            with self._lock:
                self._alias_to_std = mapping
                self._loaded = True
        finally:
            session.close()

    def ensure_loaded(self) -> None:
        if not self._loaded:
            self.reload()

    def normalize_entity(self, raw_name: str, entity_type: str = "Model") -> str:
        self.ensure_loaded()
        cleaned = clean_entity_name(raw_name)
        if not cleaned:
            return cleaned
        with self._lock:
            if cleaned in self._alias_to_std:
                return self._alias_to_std[cleaned]
            raw_lower = (raw_name or "").strip().lower()
            if raw_lower in self._alias_to_std:
                return self._alias_to_std[raw_lower]
        return cleaned

    def persist_aliases(self, pairs: list[tuple[str, str, str]]) -> int:
        """写入新别名；pairs = (raw_name, std_name, entity_type)。"""
        if not pairs:
            return 0
        session = SessionLocal()
        added = 0
        try:
            existing = {r.raw_alias.lower() for r in session.query(EntityAlias.raw_alias).all()}
            pending: dict[str, tuple[str, str]] = {}
            for raw_name, std_name, entity_type in pairs:
                et = entity_type if entity_type in _ENTITY_TYPES else "Model"
                for key in {raw_name.strip(), raw_name.strip().lower(), clean_entity_name(raw_name)}:
                    if not key:
                        continue
                    store_key = key.lower()
                    if store_key in existing or store_key in pending:
                        continue
                    pending[store_key] = (std_name, et)

            for key, (std_name, et) in pending.items():
                session.add(
                    EntityAlias(
                        id=next_snowflake_id(),
                        std_name=std_name,
                        raw_alias=key,
                        entity_type=et,
                    )
                )
                existing.add(key)
                with self._lock:
                    self._alias_to_std[key] = std_name
                added += 1
            if added:
                session.commit()
        finally:
            session.close()
        return added


def normalize_entity(raw_name: str, entity_type: str = "Model") -> str:
    return EntityAliasCache.get().normalize_entity(raw_name, entity_type)
