"""对话结束后由 LLM 决定文档内容并生成可下载文件。"""
from __future__ import annotations

import json
import re
from typing import Any

from src.services.document_gen.generator import generate_document_file
from src.utils.logging_config import setup_logger

logger = setup_logger("DocumentGenService")

_EXTRACT_SYSTEM = """你是文档编排助手。根据「用户问题」与「助手回答」，决定哪些内容应写入可下载文档。

只返回 JSON，不要 markdown 代码块，格式如下：
{"include_in_document": true, "title": "文档标题", "content": "正文", "format": "docx"}

规则：
1. include_in_document：用户明确要求导出/生成文档、备忘录、报告，或回答本身适合整理成文档时为 true；纯闲聊、单句问答、仅确认操作时为 false。
2. content：只收录应写入文件的部分，按段落用换行分隔；剔除「好的」「如下所示」等口语套话；保留数据、公式、引用标记与专业术语，不要改写事实。
3. title：简洁概括文档主题。
4. format：默认 docx；用户明确要求 pdf 时用 pdf。
5. 若 include_in_document 为 false，title 与 content 可为空字符串。
"""


def _extract_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        return {}
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if fence:
        raw = fence.group(1).strip()
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(raw[start : end + 1])
                return data if isinstance(data, dict) else {}
            except json.JSONDecodeError:
                return {}
    return {}


def _plan_document(query: str, assistant_content: str, model) -> dict[str, Any] | None:
    if not (assistant_content or "").strip():
        return None

    user_block = (
        f"【用户问题】\n{(query or '').strip()}\n\n"
        f"【助手回答】\n{assistant_content.strip()}"
    )
    messages = [
        {"role": "system", "content": _EXTRACT_SYSTEM},
        {"role": "user", "content": user_block},
    ]
    try:
        message = model.predict(messages, stream=False)
        content = getattr(message, "content", None) or str(message)
        plan = _extract_json(content)
    except Exception as exc:
        logger.warning("document plan LLM failed: %s", exc)
        return None

    if not plan.get("include_in_document"):
        return None

    title = str(plan.get("title") or "").strip()
    body = str(plan.get("content") or "").strip()
    if not body:
        body = assistant_content.strip()
    if not title:
        title = "ChronoPaper Document"

    fmt = str(plan.get("format") or "docx").lower()
    if fmt not in ("docx", "pdf"):
        fmt = "docx"

    return {"title": title, "content": body, "format": fmt}


def try_generate_document_from_turn(
    *,
    query: str,
    assistant_content: str,
    model,
) -> dict[str, Any] | None:
    """LLM 规划文档内容并生成文件；不适合生成时返回 None。"""
    plan = _plan_document(query, assistant_content, model)
    if not plan:
        return None

    try:
        artifact = generate_document_file(
            title=plan["title"],
            content=plan["content"],
            format=plan["format"],
        )
        logger.info(
            "Document generated title=%s format=%s size=%s",
            plan["title"],
            plan["format"],
            artifact.get("file_size"),
        )
        return artifact
    except Exception as exc:
        logger.warning("document file generation failed: %s", exc)
        return None
