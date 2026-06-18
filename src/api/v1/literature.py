"""文献管理 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.api.deps import UserInDB, get_current_active_user, get_db
from src.schemas.literature import LiteratureDeleteRequest
from src.services import literature_service

router = APIRouter(prefix="/literature", tags=["literature"])


@router.get("/public")
def list_public_papers(
    q: str | None = Query(default=None),
    category: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: UserInDB = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return literature_service.list_public_papers(db, q=q, category=category, page=page, page_size=page_size)


@router.get("/private")
def list_private_papers(
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: UserInDB = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return literature_service.list_private_papers(db, current_user.userid, q=q, page=page, page_size=page_size)


@router.get("/paper/{arxiv_id}")
def get_paper_detail(
    arxiv_id: str,
    current_user: UserInDB = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    data = literature_service.get_paper_detail(db, arxiv_id, current_user.userid)
    if data is None:
        from src.models.paper import Paper
        if not db.query(Paper).filter(Paper.arxiv_id == arxiv_id).first():
            raise HTTPException(status_code=404, detail="论文不存在")
        raise HTTPException(status_code=403, detail="无权查看该论文")
    return data


@router.post("/delete")
def delete_literature_entries(
    body: LiteratureDeleteRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    result = literature_service.delete_literature_entries(
        db,
        current_user.userid,
        arxiv_ids=body.arxiv_ids,
        visibility=body.visibility,
    )
    if result["deleted"] == 0 and result["not_found"]:
        raise HTTPException(status_code=404, detail="未找到可删除的文献")
    return result
