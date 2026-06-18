"""划词 / 全文翻译 API（DeepSeek 流式）。"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from src.api.deps import UserInDB, get_current_active_user
from src.schemas.translate import CrawlQueryTranslateRequest, TranslateRequest
from src.services import translate_service

router = APIRouter(prefix="/translate", tags=["translate"])


@router.post("/stream")
def translate_stream(
    body: TranslateRequest,
    current_user: UserInDB = Depends(get_current_active_user),
):
    del current_user

    def generate():
        try:
            for piece in translate_service.stream_translate(body.text, target_lang=body.target_lang):
                payload = json.dumps({"content": piece, "done": False}, ensure_ascii=False)
                yield payload.encode("utf-8") + b"\n"
            yield json.dumps({"content": "", "done": True}, ensure_ascii=False).encode("utf-8") + b"\n"
        except RuntimeError as exc:
            err = json.dumps({"error": str(exc), "done": True}, ensure_ascii=False)
            yield err.encode("utf-8") + b"\n"
        except Exception as exc:
            err = json.dumps({"error": f"翻译失败: {exc}", "done": True}, ensure_ascii=False)
            yield err.encode("utf-8") + b"\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@router.get("/config")
def translate_config(current_user: UserInDB = Depends(get_current_active_user)):
    del current_user
    from src.settings import get_settings

    settings = get_settings()
    return {
        "model": settings.translate_model or "deepseek-chat",
        "provider": "deepseek",
    }


@router.post("/crawl-query")
def translate_crawl_query(
    body: CrawlQueryTranslateRequest,
    current_user: UserInDB = Depends(get_current_active_user),
):
    del current_user
    try:
        return translate_service.prepare_crawl_match_query(body.intent_text, body.keywords)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"翻译失败: {exc}") from exc
