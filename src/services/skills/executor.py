"""Skill 执行：路由 + 加载上下文，注入 system prompt。"""
from __future__ import annotations

from typing import Any

from src.services.skills.loader import load_skill_context
from src.services.skills.registry import get_skill_registry
from src.services.skills.router import resolve_skill_id
from src.services.skills.generated_runner import _FILE_OUTPUT_SKILLS
from src.services.skills.input_sync import (
    collect_paper_ids_from_meta,
    sync_literature_to_skill,
)
from src.services.skills.script_planner import maybe_run_skill_scripts
from src.utils.logging_config import setup_logger

logger = setup_logger("SkillExecutor")

_SYSTEM_WRAPPER = """你是 ChronoPaper 科研助手。请严格遵循以下技能指令完成用户任务。
若技能指令与通用常识冲突，以技能指令为准；不得编造未给出的实验数据或引用。

{skill_context}
"""

_PLATFORM_NOTE = """## ChronoPaper 平台说明
本环境在对话前通过 **LangGraph 编排**执行技能脚本：写代码 → 静态校验 → 运行 → **解析真实产物**（页数/字数/结构）→ 未达标自动修订（最多 3 轮）。
- 若脚本含删除目录等高危操作，会先 **LLM 安全审查**，再请你在前端确认是否放行。
- 下方「技能多轮代码执行」含**产物质检摘要**（Agent 已读取生成文件，非仅看 stdout）。
- 若显示成功且通过质检：**文件已生成**，请直接告知下载方式，勿称「环境无法生成 pptx/文件」或只贴示例代码。
- 若质检未达标，如实说明缺口（如页数不足、内容过短），勿按对话规划谎称已完成。
- **勿在回复正文粘贴完整生成脚本**；正文只说明结果与产物即可。
"""


def prepare_skill_turn(
    query: str,
    meta: dict,
    *,
    model=None,
    user_id: str | None = None,
    run_id: str | None = None,
) -> tuple[str | None, dict[str, Any]]:
    """
    解析并加载技能，返回 (system_prompt, skill_info)。
    skill_info 写入 refs / meta 供前端展示。
    """
    registry = get_skill_registry()
    skill_id, route_mode = resolve_skill_id(
        query,
        meta,
        registry.list_all(),
        model=model,
    )
    if not skill_id:
        return None, {"skill_mode": route_mode, "skill_id": None, "skill_name": None}

    record = registry.get(skill_id)
    if not record or not record.enabled:
        return None, {"skill_mode": route_mode, "skill_id": None, "skill_name": None}

    try:
        ctx = load_skill_context(record)
    except Exception as exc:
        logger.warning("Load skill %s failed: %s", skill_id, exc)
        return None, {"skill_mode": route_mode, "skill_id": skill_id, "skill_error": str(exc)}

    script_ctx = None
    script_runs: list = []
    pending_approval: dict | None = None
    run_scripts = meta.get("skill_run_scripts", True) is not False
    allow_codegen = meta.get("skill_codegen", True) is not False

    input_context = ""
    skill_inputs: dict[str, Any] = {}
    approval_id = meta.get("codegen_approval_id")
    if approval_id and user_id:
        from src.services.skills.codegen_approval import consume_completed_approval

        completed = consume_completed_approval(str(approval_id), user_id)
        if completed:
            script_ctx = completed.context_block
            script_runs = completed.runs
            allow_codegen = False
            run_scripts = False
        else:
            logger.warning("Codegen approval %s not found or expired", approval_id)

    if (run_scripts or allow_codegen) and script_ctx is None:
        paper_ids = collect_paper_ids_from_meta(meta)
        if paper_ids:
            synced = sync_literature_to_skill(record.path, paper_ids)
            input_context = synced.to_prompt_block()
            skill_inputs = {
                "paper_ids": synced.paper_ids,
                "pdf_paths": synced.pdf_rels,
                "figure_paths": synced.figure_rels,
            }

    if (run_scripts or allow_codegen) and script_ctx is None:
        script_ctx, script_runs, pending_approval = maybe_run_skill_scripts(
            query,
            record,
            model,
            enabled=run_scripts or allow_codegen,
            allow_codegen=allow_codegen,
            user_id=user_id,
            run_id=run_id,
            input_context=input_context,
        )

    system = _SYSTEM_WRAPPER.format(skill_context=ctx)
    if skill_id in _FILE_OUTPUT_SKILLS or allow_codegen:
        system = f"{system}\n\n{_PLATFORM_NOTE}"
    if script_ctx:
        system = f"{system}\n\n{script_ctx}"

    info = {
        "skill_mode": route_mode,
        "skill_id": skill_id,
        "skill_name": record.name,
        "skill_source": record.source,
    }
    if script_runs:
        info["skill_scripts"] = script_runs
        artifacts: list[dict[str, Any]] = []
        for run in script_runs:
            artifacts.extend(run.get("artifacts") or [])
        if artifacts:
            info["artifacts"] = artifacts
    if pending_approval:
        info["codegen_pending_approval"] = pending_approval
    if skill_inputs:
        info["skill_inputs"] = skill_inputs
    logger.debug("Skill active: %s route=%s", skill_id, route_mode)
    return system, info
