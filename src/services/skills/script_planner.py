"""根据用户问题决定是否执行技能脚本，并将结果注入对话上下文。"""
from __future__ import annotations

import json
import re
import time
from typing import Any

from src.integrations.llm.prompts import skill_script_plan_prompt_template
from src.services.skills.artifact_collector import (
    artifacts_context_block,
    collect_skill_artifacts,
    snapshot_output_files,
)
from src.services.skills.codegen_agent import maybe_run_codegen_loop
from src.services.skills.generated_runner import _FILE_OUTPUT_SKILLS
from src.services.skills.registry import SkillRecord
from src.services.skills.script_runner import ScriptRunResult, list_skill_scripts, run_skill_script
from src.utils.logging_config import setup_logger

logger = setup_logger("SkillScriptPlanner")

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)
_CODE_FENCE_RE = re.compile(r"^```(?:python)?\s*\n(.*?)```\s*$", re.DOTALL | re.IGNORECASE)


def _extract_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    match = _JSON_RE.search(raw)
    if match:
        raw = match.group(0)
    return json.loads(raw)


def _model_text(response: Any) -> str:
    content = getattr(response, "content", None)
    if content is not None:
        return str(content)
    if isinstance(response, dict):
        return str(response.get("content", ""))
    return str(response)


def _build_script_list(skill_root) -> str:
    lines = []
    for rel in list_skill_scripts(skill_root):
        lines.append(f"- {rel}")
    return "\n".join(lines) if lines else "（无）"


def _normalize_code(raw: str) -> str:
    text = (raw or "").strip()
    m = _CODE_FENCE_RE.match(text)
    if m:
        return m.group(1).strip()
    return text


def plan_skill_script(
    query: str,
    record: SkillRecord,
    model,
) -> dict[str, Any] | None:
    """让 LLM 决定是否运行脚本。返回 plan dict 或 None。"""
    scripts = list_skill_scripts(record.path)
    if not scripts or model is None:
        return None

    prompt = skill_script_plan_prompt_template.format(
        skill_id=record.id,
        query=query,
        script_list=_build_script_list(record.path),
    )
    try:
        response = model.predict(
            [
                {"role": "system", "content": "你只输出 JSON，不要 markdown 或解释。"},
                {"role": "user", "content": prompt},
            ],
            stream=False,
        )
        plan = _extract_json(_model_text(response))
    except Exception as exc:
        logger.warning("Skill script plan failed for %s: %s", record.id, exc)
        return None

    if not plan.get("run"):
        return None
    script = str(plan.get("script") or "").strip()
    if not script:
        return None
    if script not in scripts:
        logger.warning("Skill script not in allowlist: %s", script)
        return None
    args = plan.get("args") or []
    if not isinstance(args, list):
        args = [str(args)]
    return {"script": script, "args": [str(a) for a in args]}


def _keyword_script_plan(query: str, record: SkillRecord) -> dict[str, Any] | None:
    """LLM 未触发时的保守回退（仅 stdlib 检索脚本）。"""
    scripts = set(list_skill_scripts(record.path))
    q = (query or "").lower()

    if "scripts/academic_search.py" in scripts and record.id == "nature-academic-search":
        keys = ("查文献", "找论文", "文献检索", "literature search", "search papers", "找文献")
        if any(k in q for k in keys):
            term = query.strip() or "machine learning"
            return {
                "script": "scripts/academic_search.py",
                "args": [term, "--limit", "10"],
            }
    return None


def _run_builtin_script(
    record: SkillRecord,
    plan: dict[str, Any],
    *,
    user_id: str | None,
    run_id: str | None,
) -> tuple[str, dict[str, Any]]:
    before = snapshot_output_files(record.path)
    run_started = time.time()
    try:
        result = run_skill_script(record.path, plan["script"], plan.get("args"))
    except ValueError as exc:
        logger.warning("Skill script rejected: %s", exc)
        return f"脚本执行被拒绝: {exc}", {"error": str(exc), **plan}

    artifacts: list[dict[str, Any]] = []
    if user_id and run_id:
        artifacts = collect_skill_artifacts(
            record.path,
            before,
            user_id,
            run_id,
            since_ts=run_started - 2.0,
        )

    run_record = _result_to_dict(result, plan)
    if artifacts:
        run_record["artifacts"] = artifacts

    context = (
        "## 技能脚本执行结果\n"
        "以下内容由技能目录内脚本产生，请结合结果回答用户；若失败请说明原因。\n\n"
        f"{result.to_context_block()}"
    )
    artifact_block = artifacts_context_block(artifacts)
    if artifact_block:
        context = f"{context}\n\n{artifact_block}"
    return context, run_record


def maybe_run_skill_scripts(
    query: str,
    record: SkillRecord | None,
    model,
    *,
    enabled: bool = True,
    allow_codegen: bool = True,
    user_id: str | None = None,
    run_id: str | None = None,
    input_context: str = "",
) -> tuple[str | None, list[dict[str, Any]]]:
    """
    若启用则先尝试内置 scripts/，再尝试 LLM 生成脚本。
    返回 (注入 system 的上下文, 运行记录列表)。
    """
    if not enabled or record is None:
        return None, []

    runs: list[dict[str, Any]] = []
    scripts = list_skill_scripts(record.path)
    builtin_ran = False

    # 文件型技能优先走「模型写代码」多轮循环（对齐 SKILL 原设计）
    if allow_codegen and record.id in _FILE_OUTPUT_SKILLS:
        gen_ctx, gen_runs = maybe_run_codegen_loop(
            query,
            record,
            model,
            user_id=user_id,
            run_id=run_id,
            input_context=input_context,
        )
        if gen_ctx:
            return gen_ctx, gen_runs

    if scripts:
        plan = plan_skill_script(query, record, model)
        if not plan:
            plan = _keyword_script_plan(query, record)
        if plan:
            context, run_record = _run_builtin_script(
                record,
                plan,
                user_id=user_id,
                run_id=run_id,
            )
            runs.append(run_record)
            builtin_ran = True
            if context:
                return context, runs

    if allow_codegen:
        gen_ctx, gen_runs = maybe_run_codegen_loop(
            query,
            record,
            model,
            user_id=user_id,
            run_id=run_id,
            input_context=input_context,
        )
        if gen_ctx:
            runs.extend(gen_runs)
            return gen_ctx, runs

    if builtin_ran:
        return None, runs
    return None, []


def _result_to_dict(result: ScriptRunResult, plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "builtin",
        "script": result.script,
        "args": plan.get("args") or [],
        "returncode": result.returncode,
        "timed_out": result.timed_out,
        "stdout_preview": result.stdout[:2000],
        "stderr_preview": result.stderr[:500],
    }
