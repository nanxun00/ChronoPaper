"""云端图片文字识别（Vision API）。"""
from __future__ import annotations

import base64
from typing import Literal

import httpx

from src.settings import Settings, get_settings
from src.utils.logging_config import setup_logger

logger = setup_logger("CloudImageOCR")

_OCR_PROMPT = (
    "请仔细识别这张图片中的所有文字和关键信息（包括表格、标题、段落、标注等），"
    "按从上到下、从左到右的阅读顺序完整输出。"
    "只输出识别到的内容，不要添加解释或前缀。"
)

Provider = Literal["mimo", "dashscope", "openai", "zhipu"]


def _to_data_url(content: bytes, content_type: str) -> str:
    b64 = base64.b64encode(content).decode("ascii")
    mime = content_type or "image/jpeg"
    return f"data:{mime};base64,{b64}"


def _extract_dashscope_text(content) -> str:
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts).strip()
    return str(content or "").strip()


def _recognize_dashscope(data_url: str, *, api_key: str, model: str) -> str:
    from dashscope import MultiModalConversation

    response = MultiModalConversation.call(
        api_key=api_key,
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"image": data_url},
                    {"text": _OCR_PROMPT},
                ],
            }
        ],
    )
    status_code = getattr(response, "status_code", None)
    if status_code not in (None, 200):
        message = getattr(response, "message", None) or f"DashScope 返回 status={status_code}"
        raise RuntimeError(message)
    output = getattr(response, "output", None)
    if not output or not getattr(output, "choices", None):
        raise RuntimeError(getattr(response, "message", None) or "DashScope 未返回识别结果")
    message = output.choices[0].message
    return _extract_dashscope_text(getattr(message, "content", ""))


def _recognize_openai_compatible(
    data_url: str,
    *,
    api_key: str,
    api_base: str,
    model: str,
) -> str:
    base = api_base.rstrip("/")
    url = f"{base}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _OCR_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
    }
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
    return (data["choices"][0]["message"]["content"] or "").strip()


def _recognize_zhipu(data_url: str, *, api_key: str, model: str) -> str:
    from zhipuai import ZhipuAI

    client = ZhipuAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _OCR_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
    )
    return (response.choices[0].message.content or "").strip()


def _resolve_provider(settings: Settings) -> Provider:
    provider = (settings.image_ocr_provider or "mimo").strip().lower()
    if provider in ("mimo", "dashscope", "openai", "zhipu"):
        return provider  # type: ignore[return-value]
    raise ValueError(f"不支持的 IMAGE_OCR_PROVIDER: {provider}")


def _default_model(provider: Provider, settings: Settings) -> str:
    if settings.image_ocr_model.strip():
        return settings.image_ocr_model.strip()
    defaults = {
        "mimo": "mimo-v2-omni",
        "dashscope": "qwen-vl-plus",
        "openai": "gpt-4o-mini",
        "zhipu": "glm-4v-flash",
    }
    return defaults[provider]


def recognize_image(
    file_content: bytes,
    *,
    content_type: str,
    settings: Settings | None = None,
) -> str:
    settings = settings or get_settings()
    provider = _resolve_provider(settings)
    model = _default_model(provider, settings)
    data_url = _to_data_url(file_content, content_type)

    logger.info("Cloud image OCR via provider=%s model=%s", provider, model)

    if provider == "mimo":
        if not settings.mimo_api_key:
            raise ValueError("小米 MiMo 图片识别未配置，请在 .env 中设置 MIMO_API_KEY")
        return _recognize_openai_compatible(
            data_url,
            api_key=settings.mimo_api_key,
            api_base=settings.mimo_api_base,
            model=model,
        )

    if provider == "dashscope":
        if not settings.dashscope_api_key:
            raise ValueError("阿里云百炼图片识别未配置，请在 .env 中设置 DASHSCOPE_API_KEY")
        return _recognize_dashscope(data_url, api_key=settings.dashscope_api_key, model=model)

    if provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OpenAI 图片识别未配置，请在 .env 中设置 OPENAI_API_KEY")
        return _recognize_openai_compatible(
            data_url,
            api_key=settings.openai_api_key,
            api_base=settings.openai_api_base,
            model=model,
        )

    if provider == "zhipu":
        if not settings.zhipuai_api_key:
            raise ValueError("智谱图片识别未配置，请在 .env 中设置 ZHIPUAI_API_KEY")
        return _recognize_zhipu(data_url, api_key=settings.zhipuai_api_key, model=model)

    raise ValueError(f"unsupported provider: {provider}")


def format_ocr_context(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        cleaned = "（未能识别出可读文字）"
    return (
        f"上传的图片或照片的内容识别出的结果为{cleaned},"
        "若用户提问有关图片或照片的问题，则基于图片或照片的识别结果作为提示词。"
    )
