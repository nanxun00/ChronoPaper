"""Ideas API (placeholder)."""
from fastapi import APIRouter

router = APIRouter(prefix="/ideas", tags=["ideas"])


@router.get("")
def list_ideas_placeholder():
    return {"ideas": []}
