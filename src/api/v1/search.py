"""Search API (placeholder)."""
from fastapi import APIRouter

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
def search_placeholder():
    return {"message": "Search API coming soon", "papers": []}
