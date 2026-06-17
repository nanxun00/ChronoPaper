"""Admin configuration API (placeholder)."""
from fastapi import APIRouter, Depends

from src.api.deps import UserInDB, get_current_active_user

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/config")
def admin_config(current_user: UserInDB = Depends(get_current_active_user)):
    return {"message": "Admin API coming soon", "userid": current_user.userid}
