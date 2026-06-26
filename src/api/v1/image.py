"""
提供图片接收接口，图片上传后调用云端 Vision API 识别文字，
识别结果会附带到下次请求的提示词。
"""
from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path
from typing import Dict

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from src.integrations.cloud_image_ocr import format_ocr_context, recognize_image
from src.settings import get_settings
from src.utils.logging_config import setup_logger
from src.utils.paths import UPLOADS_DIR

_settings = get_settings()
logger = setup_logger("server-image")

image = APIRouter(prefix="/image")
router = image

supported_image_types = [
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/tiff",
]

MAX_FILE_SIZE = 10 * 1024 * 1024
CACHE_EXPIRE = 300
ocr_cache: Dict[str, dict] = {}

IMAGE_UPLOAD_DIR = UPLOADS_DIR / "chat_images"
IMAGE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@image.post("/upload_image")
async def upload_image(file: UploadFile = File(...)):
    try:
        file_content = await file.read()
        if len(file_content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="文件过大，最大为10MB")

        content_type = file.content_type or "image/jpeg"
        if content_type not in supported_image_types:
            raise HTTPException(status_code=415, detail="不支持的图片格式")

        file_suffix = Path(file.filename or "image.jpg").suffix or ".jpg"
        saved_filename = f"{uuid.uuid4()}{file_suffix}"
        save_path = IMAGE_UPLOAD_DIR / saved_filename
        save_path.write_bytes(file_content)

        raw_text = await asyncio.to_thread(
            recognize_image,
            file_content,
            content_type=content_type,
        )
        text = format_ocr_context(raw_text)

        session_id = str(uuid.uuid4())
        ocr_cache[session_id] = {
            "text": text,
            "image_path": saved_filename,
            "expire_time": time.time() + CACHE_EXPIRE,
        }

        return JSONResponse(
            content={
                "session_id": session_id,
                "ocr_text": text,
                "image_path": f"/uploads/chat_images/{saved_filename}",
                "expires_in": CACHE_EXPIRE,
            }
        )
    except HTTPException:
        raise
    except ValueError as exc:
        logger.warning("Image OCR config/validation failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Cloud image OCR failed")
        raise HTTPException(status_code=502, detail=f"图片识别失败: {exc}") from exc
