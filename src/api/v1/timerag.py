"""TimeRAG API (placeholder)."""
from fastapi import APIRouter

router = APIRouter(prefix="/timerag", tags=["timerag"])


@router.get("")
def timerag_placeholder():
    return {"message": "TimeRAG API coming soon"}
