"""私有文献库 CRUD。"""
from __future__ import annotations

import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.literature import LiteratureEntry, LiteratureLibrary

DEFAULT_LIBRARY_NAME = "默认文献库"
DEFAULT_LIBRARY_DESC = "未指定领域的私有文献"


def _new_library_id() -> str:
    return f"lib-{uuid.uuid4().hex[:16]}"


def ensure_default_library(db: Session, user_id: str) -> LiteratureLibrary:
    row = (
        db.query(LiteratureLibrary)
        .filter(LiteratureLibrary.user_id == user_id, LiteratureLibrary.name == DEFAULT_LIBRARY_NAME)
        .first()
    )
    if row:
        return row
    row = LiteratureLibrary(
        library_id=_new_library_id(),
        user_id=user_id,
        name=DEFAULT_LIBRARY_NAME,
        description=DEFAULT_LIBRARY_DESC,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def backfill_private_library_ids(db: Session, user_id: str) -> None:
    default = ensure_default_library(db, user_id)
    db.query(LiteratureEntry).filter(
        LiteratureEntry.user_id == user_id,
        LiteratureEntry.visibility == "private",
        LiteratureEntry.library_id.is_(None),
    ).update({LiteratureEntry.library_id: default.library_id}, synchronize_session=False)
    db.commit()


def get_library(db: Session, user_id: str, library_id: str) -> LiteratureLibrary | None:
    return (
        db.query(LiteratureLibrary)
        .filter(LiteratureLibrary.library_id == library_id, LiteratureLibrary.user_id == user_id)
        .first()
    )


def resolve_private_library_id(
    db: Session,
    user_id: str,
    library_id: str | None,
    *,
    required: bool = False,
) -> str | None:
    if not library_id:
        if required:
            raise ValueError("请选择私有文献库")
        return None
    lib = get_library(db, user_id, library_id)
    if not lib:
        raise ValueError("文献库不存在或无权访问")
    return lib.library_id


def list_libraries(db: Session, user_id: str) -> list[dict]:
    backfill_private_library_ids(db, user_id)
    rows = (
        db.query(LiteratureLibrary)
        .filter(LiteratureLibrary.user_id == user_id)
        .order_by(LiteratureLibrary.created_at.asc())
        .all()
    )
    if not rows:
        rows = [ensure_default_library(db, user_id)]

    counts = dict(
        db.query(LiteratureEntry.library_id, func.count(LiteratureEntry.id))
        .filter(LiteratureEntry.user_id == user_id, LiteratureEntry.visibility == "private")
        .group_by(LiteratureEntry.library_id)
        .all()
    )
    out: list[dict] = []
    for lib in rows:
        item = lib.to_dict()
        item["paper_count"] = int(counts.get(lib.library_id, 0))
        out.append(item)
    return out


def create_library(db: Session, user_id: str, *, name: str, description: str = "") -> dict:
    title = (name or "").strip()
    if not title:
        raise ValueError("文献库名称不能为空")
    if len(title) > 255:
        raise ValueError("文献库名称过长")
    exists = (
        db.query(LiteratureLibrary)
        .filter(LiteratureLibrary.user_id == user_id, LiteratureLibrary.name == title)
        .first()
    )
    if exists:
        raise ValueError("已存在同名文献库")
    row = LiteratureLibrary(
        library_id=_new_library_id(),
        user_id=user_id,
        name=title,
        description=(description or "").strip(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    data = row.to_dict()
    data["paper_count"] = 0
    return data


def delete_library(db: Session, user_id: str, library_id: str) -> bool:
    lib = get_library(db, user_id, library_id)
    if not lib:
        return False
    if lib.name == DEFAULT_LIBRARY_NAME:
        raise ValueError("默认文献库不可删除")
    count = (
        db.query(LiteratureEntry)
        .filter(
            LiteratureEntry.library_id == library_id,
            LiteratureEntry.visibility == "private",
            LiteratureEntry.user_id == user_id,
        )
        .count()
    )
    if count > 0:
        raise ValueError("文献库内仍有论文，请先移出或删除")
    db.delete(lib)
    db.commit()
    return True
