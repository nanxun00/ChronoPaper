"""划词翻译：DeepSeek 流式输出。"""
from __future__ import annotations

from collections.abc import Iterator

from openai import OpenAI

from src.settings import get_settings

_LANG_LABELS = {
    "zh": "简体中文",
    "en": "English",
    "ja": "日本語",
    "ko": "한국어",
    "fr": "Français",
    "de": "Deutsch",
}


def _target_label(code: str) -> str:
    return _LANG_LABELS.get((code or "zh").lower(), code or "简体中文")


def _client() -> OpenAI:
    settings = get_settings()
    api_key = settings.deepseek_api_key
    if not api_key:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY，无法使用翻译功能")
    return OpenAI(api_key=api_key, base_url="https://api.deepseek.com")


def stream_translate(text: str, *, target_lang: str = "zh") -> Iterator[str]:
    settings = get_settings()
    model = settings.translate_model or "deepseek-chat"
    target = _target_label(target_lang)

    client = _client()
    stream = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    f"You are a professional academic translator. "
                    f"Translate the user's text into {target}. "
                    "Preserve technical terms when appropriate. "
                    "Output only the translation without explanations or quotes."
                ),
            },
            {"role": "user", "content": text.strip()},
        ],
        stream=True,
        temperature=0.3,
    )

    for chunk in stream:
        delta = chunk.choices[0].delta
        if delta and delta.content:
            yield delta.content


def translate_text(text: str, *, target_lang: str = "zh") -> str:
    """非流式翻译，供抓取匹配等后端逻辑使用。"""
    raw = (text or "").strip()
    if not raw:
        return ""

    settings = get_settings()
    model = settings.translate_model or "deepseek-chat"
    target = _target_label(target_lang)
    client = _client()

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    f"You are a professional academic translator specializing in AI/ML papers. "
                    f"Translate the user's text into {target}. "
                    "Keep standard English technical terms (e.g. transformer, LLM, RAG). "
                    "For comma-separated keywords, output comma-separated English terms only. "
                    "Output only the translation without explanations or quotes."
                ),
            },
            {"role": "user", "content": raw},
        ],
        stream=False,
        temperature=0.2,
    )
    content = response.choices[0].message.content
    return (content or "").strip()


def prepare_crawl_match_query(intent_text: str, keywords: str) -> dict:
    """若兴趣/关键词含中文，译为英文后再用于 arXiv/OpenReview 匹配。"""
    from src.utils.lang_detect import contains_chinese

    intent = (intent_text or "").strip()
    kw = (keywords or "").strip()
    match_intent = intent
    match_keywords = kw
    translated_fields: list[str] = []

    if intent and contains_chinese(intent):
        match_intent = translate_text(intent, target_lang="en")
        translated_fields.append("intent")

    if kw and contains_chinese(kw):
        match_keywords = translate_text(kw.replace("，", ","), target_lang="en")
        translated_fields.append("keywords")

    return {
        "intent_text": match_intent,
        "keywords": match_keywords,
        "translated": bool(translated_fields),
        "translated_fields": translated_fields,
        "original_intent": intent,
        "original_keywords": kw,
    }
