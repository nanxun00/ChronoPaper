"""技能生成脚本：用户审批暂存与放行执行。"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from src.services.skills.artifact_collector import collect_skill_artifacts, snapshot_output_files
from src.services.skills.artifact_inspection import inspect_skill_deliverables, skill_supports_artifact_inspection
from src.services.skills.code_security_review import SecurityReviewResult
from src.services.skills.code_validator import validate_generated_code
from src.services.skills.codegen_common import CodegenLoopResult
from src.services.skills.codegen_agent import codegen_loop_context_block
from src.services.skills.generated_runner import (
    GeneratedRunRecord,
    sanitize_run_id,
    write_generated_script,
    run_generated_script,
)
from src.services.skills.registry import SkillRecord, get_skill_registry
from src.utils.logging_config import setup_logger

logger = setup_logger("SkillCodegenApproval")

_TTL_SEC = 30 * 60
_lock = threading.Lock()
_pending: dict[str, dict[str, Any]] = {}
_completed: dict[str, dict[str, Any]] = {}


@dataclass
class CodegenApprovalResult:
    loop: CodegenLoopResult
    context_block: str
    runs: list[dict[str, Any]]


def _purge_expired() -> None:
    now = time.time()
    for store in (_pending, _completed):
        expired = [k for k, v in store.items() if v.get("expires_at", 0) < now]
        for k in expired:
            store.pop(k, None)


def create_pending_approval(
    *,
    user_id: str,
    run_id: str,
    skill_id: str,
    code: str,
    validation_errors: list[str],
    llm_review: SecurityReviewResult,
    round_num: int,
    query: str = "",
    input_context: str = "",
) -> str:
    _purge_expired()
    approval_id = f"cap-{uuid.uuid4().hex[:16]}"
    payload = {
        "approval_id": approval_id,
        "user_id": user_id,
        "run_id": run_id,
        "skill_id": skill_id,
        "code": code,
        "validation_errors": list(validation_errors),
        "llm_review": llm_review.to_dict(),
        "round_num": round_num,
        "query": query,
        "input_context": input_context,
        "created_at": time.time(),
        "expires_at": time.time() + _TTL_SEC,
    }
    with _lock:
        _pending[approval_id] = payload
    return approval_id


def get_pending_approval(approval_id: str, user_id: str) -> dict[str, Any] | None:
    _purge_expired()
    with _lock:
        rec = _pending.get(approval_id)
    if not rec or rec.get("user_id") != user_id:
        return None
    return rec


def build_pending_public_view(rec: dict[str, Any]) -> dict[str, Any]:
    code = rec.get("code") or ""
    return {
        "approval_id": rec["approval_id"],
        "skill_id": rec.get("skill_id"),
        "validation_errors": rec.get("validation_errors") or [],
        "llm_review": rec.get("llm_review") or {},
        "code_preview": code[:3000],
        "round_num": rec.get("round_num", 1),
    }


def deny_pending_approval(approval_id: str, user_id: str) -> bool:
    with _lock:
        rec = _pending.get(approval_id)
        if not rec or rec.get("user_id") != user_id:
            return False
        _pending.pop(approval_id, None)
    return True


def consume_completed_approval(approval_id: str, user_id: str) -> CodegenApprovalResult | None:
    _purge_expired()
    with _lock:
        rec = _completed.pop(approval_id, None)
    if not rec or rec.get("user_id") != user_id:
        return None
    return CodegenApprovalResult(
        loop=rec["loop"],
        context_block=rec["context_block"],
        runs=rec["runs"],
    )


def execute_approved_codegen(approval_id: str, user_id: str) -> dict[str, Any]:
    """用户确认后执行已审查脚本，结果供后续对话注入。"""
    rec = get_pending_approval(approval_id, user_id)
    if not rec:
        raise ValueError("审批请求不存在或已过期")

    registry = get_skill_registry()
    record = registry.get(rec["skill_id"])
    if not record:
        raise ValueError(f"技能不存在: {rec['skill_id']}")

    llm_review = rec.get("llm_review") or {}
    if not llm_review.get("approved"):
        raise ValueError("该脚本未通过 LLM 安全审查，无法放行")

    code = rec.get("code") or ""
    validation = validate_generated_code(
        code,
        skill_id=record.id,
        query=rec.get("query") or "",
        allow_reviewable=True,
    )
    if not validation.ok:
        raise ValueError("仍存在不可放行的硬拦截项：" + "; ".join(validation.errors))

    loop = _run_approved_code(
        record,
        code,
        run_id=rec.get("run_id") or "run",
        user_id=user_id,
        round_num=int(rec.get("round_num") or 1),
        query=rec.get("query") or "",
    )
    context_block = codegen_loop_context_block(loop)
    runs = loop.to_run_dicts()

    with _lock:
        _pending.pop(approval_id, None)
        _completed[approval_id] = {
            "user_id": user_id,
            "loop": loop,
            "context_block": context_block,
            "runs": runs,
            "expires_at": time.time() + _TTL_SEC,
        }

    return {
        "approved": True,
        "approval_id": approval_id,
        "succeeded": loop.succeeded,
        "artifacts": loop.artifacts,
        "runs": runs,
        "context_preview": context_block[:1500],
    }


def _run_approved_code(
    record: SkillRecord,
    code: str,
    *,
    run_id: str,
    user_id: str,
    round_num: int,
    query: str,
) -> CodegenLoopResult:
    loop = CodegenLoopResult()
    before = snapshot_output_files(record.path)
    started = time.time()
    safe_run = sanitize_run_id(run_id)

    script_path = write_generated_script(record.path, safe_run, code, round_num=round_num)
    result = run_generated_script(record.path, script_path)
    gen_rec = GeneratedRunRecord(
        purpose="用户已批准的高危脚本",
        script_rel=script_path.relative_to(record.path.resolve()).as_posix(),
        result=result,
    )
    loop.rounds.append(gen_rec)

    if result.returncode != 0:
        gen_rec.validation_errors = [result.stderr or "脚本执行失败"]
        return loop

    if skill_supports_artifact_inspection(record.id):
        report = inspect_skill_deliverables(record.id, record.path, safe_run, query=query)
        feedback = report.to_feedback_block()
        loop.last_inspection_feedback = feedback
        gen_rec.inspection_summary = feedback
        if not report.ok:
            gen_rec.validation_errors = report.errors
            return loop

    artifacts = collect_skill_artifacts(
        record.path,
        before,
        user_id,
        safe_run,
        since_ts=started - 2.0,
    )
    if artifacts:
        loop.artifacts = artifacts
        loop.succeeded = True
        gen_rec.artifacts = artifacts
    elif result.returncode == 0:
        loop.succeeded = True

    logger.info(
        "Approved codegen executed skill=%s run=%s ok=%s",
        record.id,
        safe_run,
        loop.succeeded,
    )
    return loop
