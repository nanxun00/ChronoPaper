"""写入并执行 LLM 生成的技能脚本（受控 subprocess）。"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.services.skills.artifact_collector import (
    artifacts_context_block,
    collect_skill_artifacts,
    snapshot_output_files,
)
from src.services.skills.code_validator import validate_generated_code
from src.services.skills.registry import SkillRecord
from src.services.skills.script_runner import ScriptRunResult, _truncate_output, list_skill_scripts
from src.utils.logging_config import setup_logger

logger = setup_logger("SkillGeneratedRunner")

GENERATED_SUBDIR = ".generated"
DEFAULT_TIMEOUT_SEC = 180
_RUN_ID_SAFE_RE = re.compile(r"[^a-zA-Z0-9._-]+")

_FILE_OUTPUT_SKILLS = frozenset(
    {
        "nature-paper2ppt",
        "nature-figure",
        "nature-paper-to-patent",
        "nature-reader",
        "nature-data",
    }
)

_FILE_HINTS = (
    "pptx",
    "ppt",
    "幻灯片",
    "做ppt",
    "论文汇报",
    "组会",
    "docx",
    "word",
    "导出",
    "生成文件",
    "下载",
    "图表",
    "专利",
    "figure",
    ".png",
    ".pdf",
)


@dataclass
class GeneratedRunRecord:
    purpose: str
    script_rel: str
    result: ScriptRunResult
    validation_errors: list[str] | None = None
    artifacts: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "type": "generated",
            "purpose": self.purpose,
            "script": self.script_rel,
            "returncode": self.result.returncode,
            "timed_out": self.result.timed_out,
            "stdout_preview": self.result.stdout[:2000],
            "stderr_preview": self.result.stderr[:500],
        }
        if self.validation_errors:
            out["validation_errors"] = self.validation_errors
        if self.artifacts:
            out["artifacts"] = self.artifacts
        return out


def should_attempt_codegen(query: str, record: SkillRecord, *, builtin_ran: bool) -> bool:
    """内置脚本未执行时，判断是否需要尝试生成代码。"""
    if builtin_ran:
        return False
    if record.id in _FILE_OUTPUT_SKILLS:
        return True
    if list_skill_scripts(record.path):
        return False
    q = (query or "").lower()
    return any(h in q for h in _FILE_HINTS)


def sanitize_run_id(run_id: str) -> str:
    safe = _RUN_ID_SAFE_RE.sub("_", (run_id or "run").strip())[:64]
    return safe or "run"


def write_generated_script(
    skill_root: Path,
    run_id: str,
    code: str,
    *,
    round_num: int = 1,
) -> Path:
    skill_root = skill_root.resolve()
    gen_dir = skill_root / GENERATED_SUBDIR
    gen_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"_r{round_num}" if round_num > 1 else ""
    script_path = gen_dir / f"run_{sanitize_run_id(run_id)}{suffix}.py"
    script_path.write_text(code.strip() + "\n", encoding="utf-8")
    return script_path


def run_generated_script(
    skill_root: Path,
    script_path: Path,
    *,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
) -> ScriptRunResult:
    skill_root = skill_root.resolve()
    script_path = script_path.resolve()
    try:
        script_path.relative_to(skill_root)
    except ValueError as exc:
        raise ValueError("生成脚本路径越界") from exc
    if GENERATED_SUBDIR not in script_path.parts:
        raise ValueError("生成脚本必须在 .generated/ 目录下")

    rel = script_path.relative_to(skill_root).as_posix()
    argv = [sys.executable, str(script_path)]
    env = {
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        "PATH": os.environ.get("PATH", ""),
    }
    logger.info("Run generated skill script %s", rel)
    try:
        proc = subprocess.run(
            argv,
            cwd=str(skill_root),
            capture_output=True,
            timeout=timeout_sec,
            shell=False,
            env=env,
        )
        return ScriptRunResult(
            script=rel,
            argv=argv,
            returncode=proc.returncode,
            stdout=_truncate_output(proc.stdout),
            stderr=_truncate_output(proc.stderr),
            timed_out=False,
        )
    except subprocess.TimeoutExpired as exc:
        return ScriptRunResult(
            script=rel,
            argv=argv,
            returncode=-1,
            stdout=_truncate_output(exc.stdout or b""),
            stderr=(_truncate_output(exc.stderr or b"") + "\n(执行超时)").strip(),
            timed_out=True,
        )


def execute_generated_code(
    record: SkillRecord,
    code: str,
    purpose: str,
    *,
    run_id: str,
    user_id: str | None = None,
) -> GeneratedRunRecord:
    validation = validate_generated_code(code)
    if not validation.ok:
        logger.warning("Generated code validation failed: %s", validation.errors)
        dummy = ScriptRunResult(
            script=".generated/rejected.py",
            argv=[],
            returncode=-1,
            stdout="",
            stderr="; ".join(validation.errors),
        )
        return GeneratedRunRecord(
            purpose=purpose,
            script_rel=".generated/rejected.py",
            result=dummy,
            validation_errors=validation.errors,
        )

    before = snapshot_output_files(record.path)
    started = time.time()
    script_path = write_generated_script(record.path, run_id, code)
    result = run_generated_script(record.path, script_path)

    artifacts: list[dict[str, Any]] = []
    if user_id and run_id and result.returncode == 0:
        artifacts = collect_skill_artifacts(
            record.path,
            before,
            user_id,
            run_id,
            since_ts=started - 2.0,
        )

    return GeneratedRunRecord(
        purpose=purpose,
        script_rel=script_path.relative_to(record.path.resolve()).as_posix(),
        result=result,
        artifacts=artifacts or None,
    )


def generated_context_block(record: GeneratedRunRecord) -> str:
    if record.validation_errors:
        lines = ["## 技能生成脚本校验失败", *record.validation_errors]
        return "\n".join(lines)

    parts = [
        "## 技能生成脚本执行结果",
        f"目的：{record.purpose}",
        record.result.to_context_block(),
    ]
    if record.artifacts:
        block = artifacts_context_block(record.artifacts)
        if block:
            parts.append(block)
    return "\n\n".join(parts)
