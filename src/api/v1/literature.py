"""文献管理 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from src.api.deps import UserInDB, get_current_active_user, get_db
from src.schemas.literature import LiteratureDeleteRequest, LiteratureReviewRequest
from src.services import literature_service

router = APIRouter(prefix="/literature", tags=["literature"])


@router.get("/public")
def list_public_papers(
    q: str | None = Query(default=None),
    category: str | None = Query(default=None),
    source: str | None = Query(default=None, description="arxiv | openreview | openalex | upload"),
    min_semantic: float | None = Query(default=None, ge=0, le=100),
    min_quality: float | None = Query(default=None, ge=0, le=100),
    review_status: str | None = Query(default=None, description="pending | approved | rejected"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: UserInDB = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    del current_user
    return literature_service.list_public_papers(
        db,
        q=q,
        category=category,
        source=source,
        min_semantic=min_semantic,
        min_quality=min_quality,
        review_status=review_status,
        page=page,
        page_size=page_size,
    )


@router.get("/private")
def list_private_papers(
    q: str | None = Query(default=None),
    source: str | None = Query(default=None, description="arxiv | openreview | openalex | upload"),
    min_semantic: float | None = Query(default=None, ge=0, le=100),
    min_quality: float | None = Query(default=None, ge=0, le=100),
    review_status: str | None = Query(default=None, description="pending | approved | rejected"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: UserInDB = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return literature_service.list_private_papers(
        db,
        current_user.userid,
        q=q,
        source=source,
        min_semantic=min_semantic,
        min_quality=min_quality,
        review_status=review_status,
        page=page,
        page_size=page_size,
    )


@router.get("/pdf/{arxiv_id:path}")
def get_paper_pdf(
    arxiv_id: str,
    current_user: UserInDB = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    pdf_path = literature_service.resolve_accessible_paper_pdf(db, arxiv_id, current_user.userid)
    if not pdf_path:
        paper_exists = literature_service.get_paper_detail(db, arxiv_id, current_user.userid)
        if paper_exists is None:
            from src.models.literature import Paper

            if not db.query(Paper).filter(Paper.arxiv_id == arxiv_id).first():
                raise HTTPException(status_code=404, detail="论文不存在")
            raise HTTPException(status_code=403, detail="无权查看该论文")
        raise HTTPException(status_code=404, detail="本地 PDF 尚未下载")
    safe_name = arxiv_id.replace("/", "_").replace(":", "_")
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"{safe_name}.pdf",
    )


@router.get("/paper/{arxiv_id:path}")
def get_paper_detail(
    arxiv_id: str,
    current_user: UserInDB = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    data = literature_service.get_paper_detail(db, arxiv_id, current_user.userid)
    if data is None:
        from src.models.literature import Paper
        if not db.query(Paper).filter(Paper.arxiv_id == arxiv_id).first():
            raise HTTPException(status_code=404, detail="论文不存在")
        raise HTTPException(status_code=403, detail="无权查看该论文")
    return data


@router.post("/upload")
async def upload_literature_pdf(
    file: UploadFile = File(...),
    visibility: str = Form(...),
    title: str | None = Form(default=None),
    current_user: UserInDB = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if visibility not in ("public", "private"):
        raise HTTPException(status_code=400, detail="visibility 须为 public 或 private")
    content = await file.read()
    try:
        return literature_service.upload_paper_pdf(
            db,
            user_id=current_user.userid,
            visibility=visibility,
            filename=file.filename or "upload.pdf",
            content=content,
            title=title,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/approve")
def approve_literature_entries(
    body: LiteratureReviewRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    result = literature_service.approve_literature_entries(
        db,
        current_user.userid,
        arxiv_ids=body.arxiv_ids,
        visibility=body.visibility,
    )
    if result["approved"] == 0 and not result["already_approved"] and result["not_found"]:
        raise HTTPException(status_code=404, detail="未找到可审核的文献")
    return result


@router.post("/reject")
def reject_literature_entries(
    body: LiteratureReviewRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    result = literature_service.reject_literature_entries(
        db,
        current_user.userid,
        arxiv_ids=body.arxiv_ids,
        visibility=body.visibility,
    )
    if result["rejected"] == 0 and result["not_found"]:
        raise HTTPException(status_code=404, detail="未找到可审核的文献")
    return result


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
