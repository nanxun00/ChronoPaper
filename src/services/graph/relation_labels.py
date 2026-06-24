"""图谱关系类型：Neo4j 内部英文标识 → 中文展示名。"""
from __future__ import annotations

RELATION_LABELS_ZH: dict[str, str] = {
    "PROPOSE": "提出",
    "IMPROVE_FROM": "改进自",
    "DIFFERENT_WITH": "对比差异",
    "USE_DATASET": "使用数据集",
    "EVALUATE_BY": "评测指标",
    "EXTEND_FROM": "延伸自",
    "PUBLISH_AT": "发表于",
    "CITE": "引用",
    "WRITTEN_BY": "作者",
    "RELATION": "关联",
}


def rel_label_zh(rel_type: str | None) -> str:
    if not rel_type:
        return "关联"
    key = str(rel_type).strip()
    if key in RELATION_LABELS_ZH:
        return RELATION_LABELS_ZH[key]
    upper = key.upper()
    if upper in RELATION_LABELS_ZH:
        return RELATION_LABELS_ZH[upper]
    return key
