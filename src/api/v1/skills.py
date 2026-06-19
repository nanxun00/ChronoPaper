"""Skill 管理 API。"""
from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from src.api.deps import UserInDB, get_current_active_user
from src.services.skills.registry import get_skill_registry

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("/")
def list_skills(current_user: UserInDB = Depends(get_current_active_user)):
    reg = get_skill_registry()
    reg._translate_descriptions()
    return {"skills": [s.to_dict() for s in reg.list_all()]}


@router.post("/reload")
def reload_skills(current_user: UserInDB = Depends(get_current_active_user)):
    reg = get_skill_registry()
    reg.reload()
    reg._translate_descriptions()
    return {"skills": [s.to_dict() for s in reg.list_all()]}


@router.patch("/{skill_id}")
def patch_skill(
    skill_id: str,
    body: dict,
    current_user: UserInDB = Depends(get_current_active_user),
):
    enabled = body.get("enabled")
    if enabled is None:
        raise HTTPException(400, "需要 enabled 字段")
    reg = get_skill_registry()
    rec = reg.set_enabled(skill_id, bool(enabled))
    if not rec:
        raise HTTPException(404, f"未找到技能: {skill_id}")
    return rec.to_dict()


@router.post("/upload")
async def upload_skill(
    file: UploadFile = File(...),
    current_user: UserInDB = Depends(get_current_active_user),
):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "请上传 .zip 格式的技能包")
    reg = get_skill_registry()
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)
    try:
        installed = reg.install_zip(tmp_path)
    except (zipfile.BadZipFile, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)
    if not installed:
        raise HTTPException(400, "zip 中未找到含 SKILL.md 的技能目录")
    return {"installed": [s.to_dict() for s in installed]}
