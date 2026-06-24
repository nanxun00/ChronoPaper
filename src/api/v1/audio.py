import asyncio
import os
import shutil
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from src.integrations.xfyun_asr import transcribe_audio_file
from src.settings import get_settings, PROJECT_ROOT
from src.utils import setup_logger

_settings = get_settings()
logger = setup_logger("server-audio")

UPLOAD_DIR = PROJECT_ROOT / "src/saves/audio"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

audio = APIRouter(prefix="/audio")
router = audio


def _save_upload(file: UploadFile) -> Path:
    suffix = Path(file.filename or "recording.webm").suffix or ".webm"
    filename = f"{os.urandom(8).hex()}{suffix}"
    file_path = UPLOAD_DIR / filename
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return file_path


@audio.post("/upload")
async def create_audio_file(file: UploadFile = File(...)):
    if not _settings.xfyun_app_id or not _settings.xfyun_api_key or not _settings.xfyun_api_secret:
        raise HTTPException(status_code=500, detail="科大讯飞语音识别未配置，请在 .env 中设置 XFYUN_APP_ID / XFYUN_API_KEY / XFYUN_API_SECRET")

    file_path = _save_upload(file)
    try:
        text = await asyncio.to_thread(
            transcribe_audio_file,
            file_path,
            app_id=_settings.xfyun_app_id,
            api_key=_settings.xfyun_api_key,
            api_secret=_settings.xfyun_api_secret,
        )
    except ValueError as exc:
        logger.warning("Audio validation failed for %s: %s", file_path, exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("XFyun ASR failed for %s", file_path)
        raise HTTPException(status_code=502, detail=f"语音识别失败: {exc}") from exc
    finally:
        file_path.unlink(missing_ok=True)

    return text or ""
