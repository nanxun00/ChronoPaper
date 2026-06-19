"""技能描述中文化：安装/刷新时翻译并缓存到 state.json。"""
from __future__ import annotations

import hashlib
import json
import re
from typing import TYPE_CHECKING, Any

from src.utils.logging_config import setup_logger

if TYPE_CHECKING:
    from src.services.skills.registry import SkillRegistry

logger = setup_logger("SkillDescriptionI18n")

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

# nature-skills 内置回退译文（LLM 不可用时）
_STATIC_ZH: dict[str, str] = {
    "nature-academic-search": "多源文献检索、引文核验、检索策略与参考文献格式转换",
    "nature-citation": "为文稿添加严格的 Nature/CNS 风格引用与参考文献",
    "nature-data": "撰写、审核或修订符合 Nature 要求的数据可用性声明",
    "nature-figure": "制作投稿级 Nature/高影响力期刊科学图表",
    "nature-paper-to-patent": "将科技论文、学位论文或技术报告转化为发明专利文稿",
    "nature-paper2ppt": "基于论文生成 Nature 风格中文汇报 PPT",
    "nature-polishing": "润色、重构或翻译学术文本为高质量英文",
    "nature-reader": "生成全文中英文对照、可追溯的论文 Markdown 阅读稿",
    "nature-response": "起草、审核或修订逐条回复审稿意见的答复信",
    "nature-reviewer": "模拟 Nature 风格同行评议与审稿报告",
    "nature-writing": "起草、规划或重构 Nature 风格论文各章节",
}


def _desc_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _needs_translation(text: str) -> bool:
    if not text or not text.strip():
        return False
    ascii_letters = sum(1 for c in text if c.isascii() and c.isalpha())
    cjk = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    return ascii_letters > max(cjk, 8)


def _model_text(response: Any) -> str:
    content = getattr(response, "content", None)
    if content is not None:
        return str(content)
    if isinstance(response, dict):
        return str(response.get("content", ""))
    return str(response)


def _get_chat_model():
    try:
        from src.services.rag.startup import startup

        return startup.model
    except Exception:
        return None


def _load_state() -> dict[str, Any]:
    from src.services.skills.registry import _load_state as load

    return load()


def _save_state(state: dict[str, Any]) -> None:
    from src.services.skills.registry import _save_state as save

    save(state)


def apply_descriptions_to_registry(registry: SkillRegistry) -> None:
    """将 state 中缓存的中文描述应用到内存记录。"""
    state = _load_state()
    zh_map: dict[str, str] = dict(state.get("descriptions_zh") or {})
    if not zh_map:
        return
    for rec in registry.list_all():
        zh = zh_map.get(rec.id)
        if zh:
            rec.description = zh


def translate_skill_descriptions(
    registry: SkillRegistry,
    *,
    skill_ids: list[str] | None = None,
) -> int:
    """
    为指定技能（默认全部）生成/更新中文描述并写入 state.json。
    返回本次新翻译的数量。
    """
    state = _load_state()
    zh_map: dict[str, str] = dict(state.get("descriptions_zh") or {})
    hash_map: dict[str, str] = dict(state.get("description_source_hash") or {})

    targets: list[tuple[str, str]] = []
    id_filter = set(skill_ids) if skill_ids else None
    for rec in registry.list_all():
        if id_filter is not None and rec.id not in id_filter:
            continue
        raw = _raw_description_from_disk(rec)
        if not _needs_translation(raw):
            zh_map[rec.id] = raw
            hash_map[rec.id] = _desc_hash(raw)
            rec.description = raw
            continue
        h = _desc_hash(raw)
        if rec.id in zh_map and hash_map.get(rec.id) == h:
            rec.description = zh_map[rec.id]
            continue
        targets.append((rec.id, raw))

    if not targets:
        state["descriptions_zh"] = zh_map
        state["description_source_hash"] = hash_map
        _save_state(state)
        return 0

    translated = _translate_batch(targets)
    updated = 0
    for sid, raw in targets:
        zh = translated.get(sid) or _STATIC_ZH.get(sid)
        if not zh:
            continue
        zh_map[sid] = zh
        hash_map[sid] = _desc_hash(raw)
        rec = registry.get(sid)
        if rec:
            rec.description = zh
        updated += 1

    state["descriptions_zh"] = zh_map
    state["description_source_hash"] = hash_map
    _save_state(state)
    logger.info("Translated %d skill descriptions to Chinese", updated)
    return updated


def _raw_description_from_disk(rec) -> str:
    from src.services.skills.registry import _parse_skill_md

    skill_md = rec.path / "SKILL.md"
    try:
        meta, _ = _parse_skill_md(skill_md)
        return str(meta.get("description") or "").strip()
    except OSError:
        return rec.description


def _translate_batch(items: list[tuple[str, str]]) -> dict[str, str]:
    """优先 LLM 批量翻译，失败则使用静态表。"""
    model = _get_chat_model()
    if model is not None:
        try:
            payload = {sid: desc for sid, desc in items}
            prompt = (
                "将下列 Agent 技能描述翻译成简洁的中文（每条 1–2 句，适合下拉菜单展示）。\n"
                "保留必要英文缩写（PDF、PPT、DOI、RAG、Nature 等）。\n"
                "只返回 JSON 对象，key 为技能 id，value 为中文描述，不要 markdown。\n\n"
                f"{json.dumps(payload, ensure_ascii=False)}"
            )
            response = model.predict(
                [
                    {"role": "system", "content": "你只输出 JSON。"},
                    {"role": "user", "content": prompt},
                ],
                stream=False,
            )
            raw = _model_text(response)
            match = _JSON_RE.search(raw)
            if not match:
                raise ValueError("no json in model response")
            data = json.loads(match.group(0))
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
        except Exception as exc:
            logger.warning("LLM skill description translation failed: %s", exc)

    out: dict[str, str] = {}
    for sid, _ in items:
        if sid in _STATIC_ZH:
            out[sid] = _STATIC_ZH[sid]
    return out
