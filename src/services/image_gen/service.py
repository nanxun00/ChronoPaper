"""聊天图像生成：梳理需求 → 用户确认 → 调用 OpenAI 兼容 images API。"""
from __future__ import annotations

import base64
import json
import re
import uuid
from pathlib import Path
from typing import Any

import httpx

from src.settings import get_settings
from src.utils.logging_config import setup_logger
from src.utils.paths import UPLOADS_DIR

logger = setup_logger("ImageGenService")

_PENDING: dict[str, dict[str, Any]] = {}

_CONFIRM_RE = re.compile(
    r"^(确定|确认|好的|好|可以|开始生成|生成吧|生成|ok|yes|y|confirm|go)\s*[。!！]?$",
    re.I,
)
_CANCEL_RE = re.compile(
    r"^(取消|算了|不要了|不用了|停止|cancel|no|n)\s*[。!！]?$",
    re.I,
)

_PREPARE_SYSTEM = """你是图像生成需求整理助手。根据用户描述，整理出适合图像生成 API 的英文 prompt，并用中文向用户确认。
只返回 JSON，不要 markdown：
{"prompt":"英文图像 prompt，具体、可执行","summary_zh":"中文需求摘要（2-5 句）","size":"1024x1024","style_notes":"可选风格说明（中文）"}
规则：
- prompt 用英文，包含主体、构图、风格、光照等
- 不要编造用户未提及的硬性约束
- size 只能是 1024x1024、1792x1024、1024x1792 之一
"""


def _pending_key(user_id: str, conv_id: str) -> str:
    return f"{user_id}:{conv_id}"


def get_pending(user_id: str, conv_id: str) -> dict[str, Any] | None:
    item = _PENDING.get(_pending_key(user_id, conv_id))
    return dict(item) if item else None


def resolve_pending(user_id: str, conv_id: str, meta: dict | None) -> dict[str, Any] | None:
    """内存 pending 优先；前端回传的 image_gen_pending 作为兜底（应对 reload / 多 worker）。"""
    pending = get_pending(user_id, conv_id)
    if pending:
        return pending
    raw = (meta or {}).get("image_gen_pending")
    if isinstance(raw, dict) and (raw.get("prompt") or raw.get("summary_zh")):
        restored = dict(raw)
        _set_pending(user_id, conv_id, restored)
        return restored
    return None


def clear_pending(user_id: str, conv_id: str) -> None:
    _PENDING.pop(_pending_key(user_id, conv_id), None)


def _set_pending(user_id: str, conv_id: str, data: dict[str, Any]) -> None:
    _PENDING[_pending_key(user_id, conv_id)] = data


def is_confirm_text(text: str) -> bool:
    return bool(_CONFIRM_RE.match((text or "").strip()))


def is_cancel_text(text: str) -> bool:
    return bool(_CANCEL_RE.match((text or "").strip()))


def _extract_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
    return {}


def _prepare_prompt(model, user_query: str) -> dict[str, Any]:
    from src.services.rag.startup import startup

    llm = model or startup.model
    response = llm.predict(
        [
            {"role": "system", "content": _PREPARE_SYSTEM},
            {"role": "user", "content": user_query.strip()},
        ],
        stream=False,
    )
    content = getattr(response, "content", None) or str(response)
    data = _extract_json(str(content))
    prompt = (data.get("prompt") or user_query or "").strip()
    summary = (data.get("summary_zh") or prompt).strip()
    size = (data.get("size") or "1024x1024").strip()
    if size not in {"1024x1024", "1792x1024", "1024x1792"}:
        size = "1024x1024"
    style_notes = (data.get("style_notes") or "").strip()
    return {
        "prompt": prompt,
        "summary_zh": summary,
        "size": size,
        "style_notes": style_notes,
        "original_query": user_query.strip(),
    }


def _generated_dir(user_id: str) -> Path:
    root = UPLOADS_DIR / "generated" / user_id
    root.mkdir(parents=True, exist_ok=True)
    return root


def _save_image_bytes(user_id: str, content: bytes, *, ext: str = ".png") -> str:
    name = f"{uuid.uuid4().hex}{ext}"
    path = _generated_dir(user_id) / name
    path.write_bytes(content)
    return f"/uploads/generated/{user_id}/{name}"


def _download_url(url: str, user_id: str) -> str:
    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        ext = ".png"
        ctype = (resp.headers.get("content-type") or "").lower()
        if "jpeg" in ctype or "jpg" in ctype:
            ext = ".jpg"
        elif "webp" in ctype:
            ext = ".webp"
        return _save_image_bytes(user_id, resp.content, ext=ext)


def _image_gen_client():
    from openai import OpenAI

    settings = get_settings()
    api_key = (settings.image_gen_api_key or settings.openai_api_key or "").strip()
    if not api_key:
        raise RuntimeError("未配置 IMAGE_GEN_API_KEY，请在 .env 中设置")
    base = (settings.image_gen_api_base or "https://api.openai-proxy.org/v1").rstrip("/")
    return OpenAI(api_key=api_key, base_url=base), settings


def _save_image_item(item: Any, user_id: str) -> str:
    b64_json = getattr(item, "b64_json", None) or (item.get("b64_json") if isinstance(item, dict) else None)
    if b64_json:
        raw = base64.b64decode(b64_json)
        return _save_image_bytes(user_id, raw, ext=".png")

    url = getattr(item, "url", None) or (item.get("url") if isinstance(item, dict) else None)
    if url:
        return _download_url(url, user_id)

    raise RuntimeError("图像 API 响应缺少 url / b64_json")


def generate_image(prompt: str, *, size: str = "1024x1024", user_id: str) -> dict[str, Any]:
    client, settings = _image_gen_client()
    model = (settings.image_gen_model or "gpt-image-2-2026-04-21").strip()

    kwargs: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "n": 1,
    }
    if size in {"1024x1024", "1792x1024", "1024x1792"}:
        kwargs["size"] = size

    try:
        response = client.images.generate(**kwargs)
    except Exception as exc:
        logger.warning("image generation failed model=%s: %s", model, exc)
        raise RuntimeError(f"图像 API 调用失败：{exc}") from exc

    items = getattr(response, "data", None) or []
    if not items:
        raise RuntimeError("图像 API 未返回图片数据")

    public_url = _save_image_item(items[0], user_id)
    return {"url": public_url, "prompt": prompt, "size": size, "model": model}


def _confirmation_message(pending: dict[str, Any]) -> str:
    lines = [
        "我已整理图像生成需求，请确认后才会调用生成 API：",
        "",
        f"**需求摘要：** {pending.get('summary_zh') or pending.get('prompt')}",
    ]
    if pending.get("style_notes"):
        lines.append(f"**风格说明：** {pending['style_notes']}")
    lines.extend(
        [
            f"**尺寸：** {pending.get('size') or '1024x1024'}",
            "",
            "回复 **确定** 开始生成，或回复 **取消** 放弃。",
            "也可点击下方 **确认生成** 按钮。",
        ]
    )
    return "\n".join(lines)


def try_handle_image_generation(
    *,
    query: str,
    meta: dict,
    user_id: str,
    conv_id: str,
    model=None,
) -> dict[str, Any] | None:
    """
    若本轮应走图像生成流程，返回响应 payload；否则返回 None 继续普通聊天。
    payload: {content, status, refs?, images?}
    """
    text = (query or "").strip()
    meta = meta or {}
    if not text and not meta.get("image_gen_confirm"):
        return None

    pending = resolve_pending(user_id, conv_id, meta)
    confirm_flag = meta.get("image_gen_confirm") is True
    image_mode = meta.get("image_gen_mode") is True
    is_confirm = is_confirm_text(text)
    is_cancel = is_cancel_text(text)

    if (confirm_flag or is_confirm) and pending:
        clear_pending(user_id, conv_id)
        try:
            result = generate_image(
                pending["prompt"],
                size=pending.get("size") or "1024x1024",
                user_id=user_id,
            )
        except Exception as exc:
            logger.exception("generate_image failed: %s", exc)
            return {
                "content": f"图像生成失败：{exc}",
                "status": "finished",
                "refs": None,
                "images": [],
            }

        url = result["url"]
        return {
            "content": f"图像已生成。\n\n**提示词：** {result['prompt']}\n\n请查看下方图片，点击可预览并下载。",
            "status": "finished",
            "refs": {"image_gen": {"last_url": url, "prompt": result["prompt"]}},
            "images": [url],
        }

    if pending and is_cancel:
        clear_pending(user_id, conv_id)
        return {
            "content": "已取消本次图像生成。",
            "status": "finished",
            "refs": None,
            "images": [],
        }

    if confirm_flag or is_confirm:
        return {
            "content": (
                "未找到待确认的图像需求（可能服务已重启或会话已刷新）。"
                "请重新开启「图像生成」，描述要生成的画面后再确认。"
            ),
            "status": "finished",
            "refs": None,
            "images": [],
        }

    if is_cancel:
        return None

    if not image_mode:
        return None

    if pending and not is_cancel:
        clear_pending(user_id, conv_id)

    try:
        prepared = _prepare_prompt(model, text)
    except Exception as exc:
        logger.exception("prepare image prompt failed: %s", exc)
        return {
            "content": f"整理图像需求失败：{exc}",
            "status": "finished",
            "refs": None,
            "images": [],
        }

    _set_pending(user_id, conv_id, prepared)
    return {
        "content": _confirmation_message(prepared),
        "status": "image_gen_confirm",
        "refs": {"image_gen_pending": prepared},
        "images": [],
    }
