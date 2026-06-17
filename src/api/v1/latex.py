"""LaTeX project API (placeholder)."""
from fastapi import APIRouter

router = APIRouter(prefix="/latex", tags=["latex"])


@router.get("/projects")
def list_projects_placeholder():
    return {"projects": []}
