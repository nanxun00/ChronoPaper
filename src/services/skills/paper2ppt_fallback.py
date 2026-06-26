"""nature-paper2ppt：codegen 失败时用 JSON 大纲 + build_pptx.py 保底出文件。"""
from __future__ import annotations

import json
import re
import time
from typing import Any

from src.services.skills.artifact_collector import (
    artifacts_context_block,
    collect_skill_artifacts,
    snapshot_output_files,
)
from src.services.skills.generated_runner import sanitize_run_id
from src.services.skills.pptx_quality import parse_target_slide_count
from src.services.skills.registry import SkillRecord
from src.services.skills.script_runner import ScriptRunResult, run_skill_script
from src.utils.logging_config import setup_logger

logger = setup_logger("Paper2PptFallback")

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _model_text(response: Any) -> str:
    content = getattr(response, "content", None)
    if content is not None:
        return str(content)
    if isinstance(response, dict):
        return str(response.get("content", ""))
    return str(response)


def _extract_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    match = _JSON_RE.search(raw)
    if match:
        raw = match.group(0)
    return json.loads(raw)


def _outline_prompt(query: str, input_context: str, slide_target: int) -> str:
    combined = f"{input_context}\n\n{query}".strip()
    excerpt = combined[:12000]
    return f"""根据以下论文/汇报材料，生成 PPT 大纲 JSON（用于学术组会汇报）。

材料：
{excerpt}

只输出 JSON，不要 markdown，格式：
{{"title":"中文标题","subtitle":"英文或副标题","slides":[{{"title":"幻灯片标题","bullets":["要点1","要点2"]}}]}}

要求：
- slides 数组约 {slide_target} 项（含背景、方法、实验、结论等）
- title/bullets 可用中文；术语保留英文
- bullets 每项 2-4 条，来自材料事实，禁止空泛占位
"""


def _request_outline(query: str, model, *, input_context: str = "") -> dict[str, Any] | None:
    if model is None:
        return None
    slide_target = parse_target_slide_count(query)
    prompt = _outline_prompt(query, input_context, slide_target)
    try:
        response = model.predict(
            [
                {"role": "system", "content": "你只输出合法 JSON，不要解释。"},
                {"role": "user", "content": prompt},
            ],
            stream=False,
        )
        outline = _extract_json(_model_text(response))
    except Exception as exc:
        logger.warning("PPT outline JSON failed: %s", exc)
        return None

    if not isinstance(outline, dict):
        return None
    slides = outline.get("slides")
    if not isinstance(slides, list) or not slides:
        return None
    return outline


def runs_contain_pptx(runs: list[dict[str, Any]]) -> bool:
    for run in runs:
        for art in run.get("artifacts") or []:
            name = str(art.get("name") or art.get("path") or "").lower()
            if name.endswith(".pptx"):
                return True
    return False


def run_paper2ppt_outline_fallback(
    query: str,
    record: SkillRecord,
    model,
    *,
    user_id: str | None,
    run_id: str | None,
    input_context: str = "",
) -> tuple[str | None, dict[str, Any] | None]:
    """运行 build_pptx.py；成功时返回 (system 上下文块, run_record)。"""
    if record.id != "nature-paper2ppt":
        return None, None

    outline = _request_outline(query, model, input_context=input_context)
    if not outline:
        logger.warning("Paper2ppt fallback: no outline for run %s", run_id)
        return None, None

    safe_run = sanitize_run_id(run_id or "run")
    outline_rel = f"input/runs/{safe_run}/ppt_outline.json"
    outline_path = record.path / outline_rel
    outline_path.parent.mkdir(parents=True, exist_ok=True)
    outline_path.write_text(json.dumps(outline, ensure_ascii=False, indent=2), encoding="utf-8")

    output_rel = f"output/runs/{safe_run}/final_presentation_cn.pptx"
    plan = {
        "script": "scripts/build_pptx.py",
        "args": ["--outline", outline_rel, "--output", output_rel],
    }

    run_started = time.time()
    before = snapshot_output_files(record.path)
    try:
        result = run_skill_script(record.path, plan["script"], plan["args"], timeout_sec=120)
    except ValueError as exc:
        logger.warning("Paper2ppt fallback script rejected: %s", exc)
        return None, {"error": str(exc), **plan}

    artifacts: list[dict[str, Any]] = []
    if user_id and run_id and result.returncode == 0:
        artifacts = collect_skill_artifacts(
            record.path,
            before,
            user_id,
            run_id,
            since_ts=run_started - 2.0,
        )

    run_record: dict[str, Any] = {
        "type": "builtin_fallback",
        "script": result.script,
        "args": plan["args"],
        "returncode": result.returncode,
        "timed_out": result.timed_out,
        "stdout_preview": result.stdout[:2000],
        "stderr_preview": result.stderr[:500],
    }
    if artifacts:
        run_record["artifacts"] = artifacts

    if result.returncode != 0 or not artifacts:
        logger.warning(
            "Paper2ppt fallback failed run=%s rc=%s artifacts=%d",
            run_id,
            result.returncode,
            len(artifacts),
        )
        return None, run_record

    context = (
        "## 技能脚本执行结果（PPT 保底路径）\n"
        "codegen 未产出合格 PPT，已改用 `scripts/build_pptx.py` + JSON 大纲生成。\n\n"
        f"{result.to_context_block()}"
    )
    block = artifacts_context_block(artifacts)
    if block:
        context = f"{context}\n\n{block}"
    return context, run_record
