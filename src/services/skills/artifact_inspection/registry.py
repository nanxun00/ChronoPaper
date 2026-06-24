"""各技能主交付物路径与质检策略。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SkillDeliverableSpec:
    skill_id: str
    relative_paths: tuple[str, ...]
    inspector: str  # pptx | docx | markdown | image | json | generic
    min_count: int = 1


# {run_id} 会在运行时替换
SKILL_DELIVERABLE_SPECS: dict[str, SkillDeliverableSpec] = {
    "nature-paper2ppt": SkillDeliverableSpec(
        skill_id="nature-paper2ppt",
        relative_paths=("output/runs/{run_id}/final_presentation_cn.pptx",),
        inspector="pptx",
        min_count=1,
    ),
    "nature-paper-to-patent": SkillDeliverableSpec(
        skill_id="nature-paper-to-patent",
        relative_paths=(
            "output/runs/{run_id}/",
        ),
        inspector="docx",
        min_count=1,
    ),
    "nature-figure": SkillDeliverableSpec(
        skill_id="nature-figure",
        relative_paths=("output/runs/{run_id}/",),
        inspector="image",
        min_count=1,
    ),
    "nature-reader": SkillDeliverableSpec(
        skill_id="nature-reader",
        relative_paths=("output/runs/{run_id}/",),
        inspector="markdown",
        min_count=1,
    ),
    "nature-reviewer": SkillDeliverableSpec(
        skill_id="nature-reviewer",
        relative_paths=("output/runs/{run_id}/reviewer_report.md",),
        inspector="markdown",
        min_count=1,
    ),
    "nature-data": SkillDeliverableSpec(
        skill_id="nature-data",
        relative_paths=("output/runs/{run_id}/",),
        inspector="markdown",
        min_count=1,
    ),
}


def get_deliverable_spec(skill_id: str) -> SkillDeliverableSpec | None:
    return SKILL_DELIVERABLE_SPECS.get(skill_id)


def resolve_deliverable_paths(spec: SkillDeliverableSpec, run_id: str) -> list[str]:
    return [p.format(run_id=run_id) for p in spec.relative_paths]
