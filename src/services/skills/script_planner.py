"""根据用户问题决定是否执行技能脚本，并将结果注入对话上下文。"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from src.integrations.llm.prompts import skill_script_plan_prompt_template
from src.services.skills.artifact_collector import (
    artifacts_context_block,
    collect_skill_artifacts,
    snapshot_output_files,
)
from src.services.skills.codegen_progress import ProgressCallback
from src.services.skills.generated_runner import _FILE_OUTPUT_SKILLS
from src.services.skills.registry import SkillRecord
from src.services.skills.script_runner import ScriptRunResult, list_skill_scripts, run_skill_script
from src.utils.logging_config import setup_logger

logger = setup_logger("SkillScriptPlanner")

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)
_CODE_FENCE_RE = re.compile(r"^```(?:python)?\s*\n(.*?)```\s*$", re.DOTALL | re.IGNORECASE)
_DOI_RE = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Z0-9]+)\b", re.IGNORECASE)
_DOWNLOAD_KEYS = (
    "下载",
    "导出",
    "引用文件",
    "引用文件下载",
    "导入",
    "bibtex",
    "bib",
    "ris",
    "nbib",
    "endnote",
    "zotero",
    "download citation",
    "export",
)
_CITATION_EXPORT_HINTS = (
    "引用",
    "推荐引用",
    "citation",
    "references",
    "支撑等级",
    "doi",
)


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


def _extract_dois(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for match in _DOI_RE.finditer(text or ""):
        doi = match.group(1).rstrip(".,;)")
        key = doi.lower()
        if key not in seen:
            seen.add(key)
            out.append(doi)
    return out


def _infer_citation_format(query: str) -> str:
    q = (query or "").lower()
    if "bib" in q or "latex" in q:
        return "bib"
    if "nbib" in q or "medline" in q or "pubmed" in q:
        return "nbib"
    if "enw" in q or "endnote" in q:
        return "enw"
    return "ris"


def _format_converter_root(record: SkillRecord):
    """format-converter 位于 academic-search；citation 技能可跨包调用。"""
    local = record.path / "scripts" / "format-converter.py"
    if local.is_file():
        return record.path
    from src.services.skills.registry import get_skill_registry

    acad = get_skill_registry().get("nature-academic-search")
    if acad and (acad.path / "scripts" / "format-converter.py").is_file():
        return acad.path
    return None


def _format_converter_plan(
    query: str,
    record: SkillRecord,
    *,
    context_text: str = "",
) -> dict[str, Any] | None:
    script_root = _format_converter_root(record)
    if not script_root or record.id not in ("nature-academic-search", "nature-citation"):
        return None

    combined = f"{context_text}\n{query}".strip()
    combined_lower = combined.lower()
    q = (query or "").lower()
    dois = _extract_dois(combined)
    if not dois:
        return None

    wants_download = (
        any(k in q for k in _DOWNLOAD_KEYS)
        or "doi" in q
        or (len(dois) >= 2 and any(h in combined_lower for h in _CITATION_EXPORT_HINTS))
    )
    if not wants_download and len(dois) == 1 and query.strip().lower().startswith("10."):
        wants_download = True
    if not wants_download:
        return None

    fmt = _infer_citation_format(query)
    doi_arg = ",".join(dois) if len(dois) > 1 else dois[0]
    plan: dict[str, Any] = {
        "script": "scripts/format-converter.py",
        "args": ["--doi", doi_arg, "--format", fmt, "--output", "references/"],
    }
    if script_root != record.path:
        plan["_script_root"] = str(script_root)
    return plan


def _keyword_script_plan(
    query: str,
    record: SkillRecord,
    *,
    context_text: str = "",
) -> dict[str, Any] | None:
    """LLM 未触发时的保守回退。"""
    converter = _format_converter_plan(query, record, context_text=context_text)
    if converter:
        return converter

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
    query: str = "",
) -> tuple[str, dict[str, Any]]:
    run_started = time.time()
    script_root = record.path
    if plan.get("_script_root"):
        script_root = Path(str(plan["_script_root"]))
    before = snapshot_output_files(script_root)
    try:
        result = run_skill_script(script_root, plan["script"], plan.get("args"))
    except ValueError as exc:
        logger.warning("Skill script rejected: %s", exc)
        safe_plan = {k: v for k, v in plan.items() if not str(k).startswith("_")}
        return f"脚本执行被拒绝: {exc}", {"error": str(exc), **safe_plan}

    artifacts: list[dict[str, Any]] = []
    if user_id and run_id:
        artifacts = collect_skill_artifacts(
            script_root,
            before,
            user_id,
            run_id,
            since_ts=run_started - 2.0,
        )

    run_record = _result_to_dict(result, plan)
    if plan.get("_script_root"):
        run_record.pop("_script_root", None)
        run_record["script_root"] = str(script_root)
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

    if run_id and result.returncode == 0:
        from src.services.skills.artifact_inspection import (
            inspect_skill_deliverables,
            skill_supports_artifact_inspection,
        )

        if skill_supports_artifact_inspection(record.id):
            report = inspect_skill_deliverables(
                record.id,
                record.path,
                run_id,
                query=query,
            )
            context = f"{context}\n\n{report.to_feedback_block()}"
            run_record["inspection_ok"] = report.ok
            if not report.ok:
                run_record["inspection_errors"] = report.errors

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
    on_progress: ProgressCallback | None = None,
    script_context: str = "",
) -> tuple[str | None, list[dict[str, Any]], dict[str, Any] | None]:
    """
    若启用则先尝试内置 scripts/，再尝试 LLM 生成脚本。
    返回 (注入 system 的上下文, 运行记录列表, 待用户审批信息)。
    """
    if not enabled or record is None:
        return None, [], None

    runs: list[dict[str, Any]] = []
    scripts = list_skill_scripts(record.path)
    builtin_ran = False

    def _codegen_result():
        from src.services.skills.codegen_agent import codegen_loop_context_block, run_codegen_loop

        loop = run_codegen_loop(
            record,
            query,
            model,
            user_id=user_id,
            run_id=run_id,
            input_context=input_context,
            on_progress=on_progress,
        )
        runs = loop.to_run_dicts()
        if loop.artifacts:
            attached = any(run.get("artifacts") for run in runs)
            if not attached:
                for run in reversed(runs):
                    if run.get("returncode") == 0:
                        run["artifacts"] = loop.artifacts
                        attached = True
                        break
                if not attached and runs:
                    runs[-1]["artifacts"] = loop.artifacts
        if loop.pending_approval:
            return None, runs, loop.pending_approval
        if not loop.rounds:
            return None, [], None
        return codegen_loop_context_block(loop), runs, None

    # 文件型技能优先走「模型写代码」多轮循环（对齐 SKILL 原设计）
    if allow_codegen and record.id in _FILE_OUTPUT_SKILLS:
        gen_ctx, gen_runs, pending = _codegen_result()
        if pending:
            return None, gen_runs, pending
        if gen_ctx:
            return gen_ctx, gen_runs, None

    if scripts:
        plan = plan_skill_script(query, record, model)
        if not plan:
            plan = _keyword_script_plan(query, record, context_text=script_context)
        if plan:
            context, run_record = _run_builtin_script(
                record,
                plan,
                user_id=user_id,
                run_id=run_id,
                query=query,
            )
            runs.append(run_record)
            builtin_ran = True
            if context:
                return context, runs, None

    if allow_codegen:
        gen_ctx, gen_runs, pending = _codegen_result()
        if pending:
            return None, gen_runs, pending
        if gen_ctx:
            runs.extend(gen_runs)
            return gen_ctx, runs, None

    if builtin_ran:
        return None, runs, None
    return None, [], None


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
