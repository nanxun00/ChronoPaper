"""LangGraph：codegen 写码 → 校验 → 执行 → 解析产物 → 未达标再改。"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict

from langgraph.graph import END, StateGraph

from src.services.skills.artifact_collector import collect_skill_artifacts, snapshot_output_files
from src.services.skills.artifact_inspection import inspect_skill_deliverables, skill_supports_artifact_inspection
from src.services.skills.artifact_inspection.registry import (
    get_deliverable_spec,
    resolve_deliverable_paths,
)
from src.services.skills.codegen_common import CodegenLoopResult, request_codegen_code
from src.services.skills.codegen_progress import (
    CodegenProgressEvent,
    ProgressCallback,
    emit_progress,
    truncate_code_preview,
)
from src.services.skills.code_validator import CodeValidationResult, validate_generated_code
from src.services.skills.generated_runner import (
    GeneratedRunRecord,
    sanitize_run_id,
    write_generated_script,
    run_generated_script,
)
from src.services.skills.registry import SkillRecord
from src.services.skills.script_runner import ScriptRunResult
from src.utils.logging_config import setup_logger

logger = setup_logger("SkillCodegenGraph")

DEFAULT_MAX_ROUNDS = 3


class CodegenGraphState(TypedDict, total=False):
    round_num: int
    code: str | None
    validation_errors: list[str] | None
    inspection_feedback: str | None
    route: Literal["generate", "success", "failed"]


@dataclass
class CodegenGraphContext:
    record: SkillRecord
    query: str
    model: Any
    run_id: str
    user_id: str | None
    input_context: str
    max_rounds: int
    loop_result: CodegenLoopResult = field(default_factory=CodegenLoopResult)
    before_snapshot: dict[str, float] = field(default_factory=dict)
    started: float = 0.0
    previous_code: str | None = None
    previous_result: ScriptRunResult | None = None
    purpose: str = "生成技能产物"
    on_progress: ProgressCallback | None = None


def _progress(ctx: CodegenGraphContext, event: CodegenProgressEvent) -> None:
    emit_progress(ctx.on_progress, event)


def _ctx(config: dict) -> CodegenGraphContext:
    return config["configurable"]["ctx"]


def _node_generate(state: CodegenGraphState, config: dict) -> CodegenGraphState:
    ctx = _ctx(config)
    round_num = state.get("round_num", 0) + 1
    if round_num > ctx.max_rounds:
        return {"round_num": round_num, "route": "failed"}

    _progress(
        ctx,
        CodegenProgressEvent(
            phase="generating",
            round=round_num,
            message=f"正在生成第 {round_num} 轮 Python 脚本…",
        ),
    )

    code = request_codegen_code(
        ctx.query,
        ctx.record,
        ctx.model,
        run_id=ctx.run_id,
        round_num=round_num,
        previous_code=ctx.previous_code,
        previous_result=ctx.previous_result,
        validation_errors=state.get("validation_errors"),
        input_context=ctx.input_context,
        artifact_inspection=state.get("inspection_feedback"),
    )
    if not code:
        logger.warning("Codegen graph round %d: no code for %s", round_num, ctx.record.id)
        return {"round_num": round_num, "code": None, "route": "failed"}

    ctx.previous_code = code
    preview = truncate_code_preview(code)
    _progress(
        ctx,
        CodegenProgressEvent(
            phase="code_ready",
            round=round_num,
            message=f"第 {round_num} 轮脚本已生成，正在校验…",
            code_preview=preview,
            script_rel=f".generated/run_{sanitize_run_id(ctx.run_id)}_r{round_num}.py",
        ),
    )
    return {
        "round_num": round_num,
        "code": code,
        "validation_errors": None,
        "inspection_feedback": None,
    }


def _node_validate(state: CodegenGraphState, config: dict) -> CodegenGraphState:
    ctx = _ctx(config)
    code = state.get("code") or ""
    round_num = state.get("round_num", 1)

    _progress(
        ctx,
        CodegenProgressEvent(
            phase="validating",
            round=round_num,
            message=f"正在校验第 {round_num} 轮脚本…",
            code_preview=truncate_code_preview(code),
        ),
    )

    validation = validate_generated_code(code, skill_id=ctx.record.id, query=ctx.query)
    if validation.ok:
        return {"validation_errors": None}

    if validation.needs_user_approval:
        from src.services.skills.code_security_review import review_generated_code_security
        from src.services.skills.codegen_approval import build_pending_public_view, create_pending_approval

        review = review_generated_code_security(
            code,
            validation.reviewable_errors or [],
            ctx.model,
            skill_id=ctx.record.id,
            query=ctx.query,
        )
        if review.approved and ctx.user_id:
            approval_id = create_pending_approval(
                user_id=ctx.user_id,
                run_id=ctx.run_id,
                skill_id=ctx.record.id,
                code=code,
                validation_errors=validation.reviewable_errors or [],
                llm_review=review,
                round_num=round_num,
                query=ctx.query,
                input_context=ctx.input_context,
            )
            ctx.loop_result.pending_approval = build_pending_public_view(
                {
                    "approval_id": approval_id,
                    "skill_id": ctx.record.id,
                    "validation_errors": validation.reviewable_errors,
                    "llm_review": review.to_dict(),
                    "code": code,
                    "round_num": round_num,
                }
            )
            _progress(
                ctx,
                CodegenProgressEvent(
                    phase="pending_approval",
                    round=round_num,
                    message="脚本需安全审查，等待你确认是否执行…",
                    code_preview=truncate_code_preview(code),
                ),
            )
            logger.info(
                "Codegen graph round %d pending user approval: %s",
                round_num,
                approval_id,
            )
            return {"route": "pending_approval", "validation_errors": validation.reviewable_errors}

        if not review.approved:
            validation = CodeValidationResult(
                ok=False,
                errors=validation.errors + [f"LLM 安全审查未通过：{review.summary}"],
                hard_block_errors=validation.hard_block_errors,
                reviewable_errors=validation.reviewable_errors,
                quality_errors=validation.quality_errors,
            )

    gen_rec = GeneratedRunRecord(
        purpose=ctx.purpose,
        script_rel=f".generated/run_{sanitize_run_id(ctx.run_id)}_r{round_num}.py",
        result=ScriptRunResult(
            script=f".generated/run_{sanitize_run_id(ctx.run_id)}_r{round_num}.py",
            argv=[],
            returncode=-1,
            stdout="",
            stderr="; ".join(validation.errors),
        ),
        validation_errors=validation.errors,
        source_code=code,
    )
    ctx.loop_result.rounds.append(gen_rec)
    ctx.previous_result = gen_rec.result
    route: Literal["generate", "failed"] = (
        "failed" if round_num >= ctx.max_rounds else "generate"
    )
    _progress(
        ctx,
        CodegenProgressEvent(
            phase="validation_failed",
            round=round_num,
            message=f"第 {round_num} 轮校验未通过"
            + ("，已达最大轮次" if route == "failed" else "，准备修订…"),
            code_preview=truncate_code_preview(code),
        ),
    )
    logger.warning("Codegen graph round %d static validation failed: %s", round_num, validation.errors)
    return {"validation_errors": validation.errors, "route": route}


def _node_execute(state: CodegenGraphState, config: dict) -> CodegenGraphState:
    ctx = _ctx(config)
    code = state.get("code") or ""
    round_num = state.get("round_num", 1)

    script_path = write_generated_script(ctx.record.path, ctx.run_id, code, round_num=round_num)
    _progress(
        ctx,
        CodegenProgressEvent(
            phase="executing",
            round=round_num,
            message=f"正在运行第 {round_num} 轮脚本…",
            code_preview=truncate_code_preview(code),
            script_rel=script_path.relative_to(ctx.record.path.resolve()).as_posix(),
        ),
    )
    result = run_generated_script(ctx.record.path, script_path)
    gen_rec = GeneratedRunRecord(
        purpose=ctx.purpose,
        script_rel=script_path.relative_to(ctx.record.path.resolve()).as_posix(),
        result=result,
        source_code=code,
    )
    ctx.loop_result.rounds.append(gen_rec)
    ctx.previous_result = result

    if result.returncode != 0:
        route: Literal["generate", "failed"] = (
            "failed" if round_num >= ctx.max_rounds else "generate"
        )
        _progress(
            ctx,
            CodegenProgressEvent(
                phase="execution_failed",
                round=round_num,
                message=f"第 {round_num} 轮脚本运行失败"
                + ("，已达最大轮次" if route == "failed" else "，准备修订…"),
                code_preview=truncate_code_preview(code),
            ),
        )
        return {
            "validation_errors": [result.stderr or "脚本执行失败"],
            "route": route,
        }
    return {"validation_errors": None}


def _node_inspect(state: CodegenGraphState, config: dict) -> CodegenGraphState:
    ctx = _ctx(config)
    round_num = state.get("round_num", 1)
    gen_rec = ctx.loop_result.rounds[-1] if ctx.loop_result.rounds else None

    if not skill_supports_artifact_inspection(ctx.record.id):
        _progress(
            ctx,
            CodegenProgressEvent(
                phase="success",
                round=round_num,
                message=f"第 {round_num} 轮脚本执行完成",
                code_preview=truncate_code_preview(state.get("code")),
            ),
        )
        return _finalize_success(ctx, gen_rec)

    _progress(
        ctx,
        CodegenProgressEvent(
            phase="inspecting",
            round=round_num,
            message=f"正在质检第 {round_num} 轮产物…",
            code_preview=truncate_code_preview(state.get("code")),
        ),
    )
    report = inspect_skill_deliverables(
        ctx.record.id,
        ctx.record.path,
        sanitize_run_id(ctx.run_id),
        query=ctx.query,
    )
    feedback = report.to_feedback_block()
    ctx.loop_result.last_inspection_feedback = feedback
    if gen_rec is not None:
        gen_rec.inspection_summary = feedback
        if not report.ok:
            gen_rec.validation_errors = report.errors

    if report.ok:
        logger.info("Codegen graph round %d artifact inspection passed", round_num)
        _progress(
            ctx,
            CodegenProgressEvent(
                phase="success",
                round=round_num,
                message=f"第 {round_num} 轮产物通过质检",
                code_preview=truncate_code_preview(state.get("code")),
            ),
        )
        return _finalize_success(ctx, gen_rec)

    logger.info("Codegen graph round %d artifact inspection failed", round_num)
    route: Literal["generate", "failed"] = (
        "failed" if round_num >= ctx.max_rounds else "generate"
    )
    _progress(
        ctx,
        CodegenProgressEvent(
            phase="inspection_failed",
            round=round_num,
            message=f"第 {round_num} 轮产物质检未达标"
            + ("，已达最大轮次" if route == "failed" else "，准备修订…"),
            code_preview=truncate_code_preview(state.get("code")),
        ),
    )
    return {
        "inspection_feedback": feedback,
        "validation_errors": report.errors,
        "route": route,
    }


def _collect_codegen_artifacts(ctx: CodegenGraphContext) -> list[dict[str, Any]]:
    """收集本轮 codegen 可下载产物；无 user/run 时仅检查交付物文件是否存在。"""
    artifacts: list[dict[str, Any]] = []
    if ctx.user_id and ctx.run_id:
        artifacts = collect_skill_artifacts(
            ctx.record.path,
            ctx.before_snapshot,
            ctx.user_id,
            ctx.run_id,
            since_ts=ctx.started - 2.0,
        )
        if not artifacts:
            artifacts = collect_skill_artifacts(
                ctx.record.path,
                {},
                ctx.user_id,
                ctx.run_id,
                since_ts=ctx.started - 2.0,
            )
    if artifacts:
        return artifacts

    spec = get_deliverable_spec(ctx.record.id)
    if spec is None:
        return []

    safe_run = sanitize_run_id(ctx.run_id or "run")
    for rel in resolve_deliverable_paths(spec, safe_run):
        path = ctx.record.path / rel.replace("\\", "/")
        if path.is_file() and ctx.user_id and ctx.run_id:
            return collect_skill_artifacts(
                ctx.record.path,
                {},
                ctx.user_id,
                ctx.run_id,
            )
    return []


def _finalize_success(
    ctx: CodegenGraphContext,
    gen_rec: GeneratedRunRecord | None,
) -> CodegenGraphState:
    artifacts = _collect_codegen_artifacts(ctx)
    if artifacts:
        ctx.loop_result.artifacts = artifacts
        ctx.loop_result.succeeded = True
        if gen_rec is not None:
            gen_rec.artifacts = artifacts
        return {"route": "success"}

    logger.warning(
        "Codegen round succeeded in inspection but no downloadable artifacts for %s run %s",
        ctx.record.id,
        ctx.run_id,
    )
    ctx.loop_result.succeeded = False
    return {"route": "failed"}


def _route_after_generate(state: CodegenGraphState) -> str:
    if state.get("route") == "failed" or not state.get("code"):
        return "end"
    return "validate"


def _route_after_validate(state: CodegenGraphState) -> str:
    if state.get("route") == "pending_approval":
        return "end"
    if state.get("validation_errors"):
        return "end" if state.get("route") == "failed" else "generate"
    return "execute"


def _route_after_execute(state: CodegenGraphState, config: dict) -> str:
    ctx = _ctx(config)
    if ctx.previous_result and ctx.previous_result.returncode != 0:
        return "end" if state.get("route") == "failed" else "generate"
    return "inspect"


def _route_after_inspect(state: CodegenGraphState) -> str:
    route = state.get("route")
    if route == "success":
        return "end"
    if route == "failed":
        return "end"
    return "generate"


def build_codegen_graph():
    graph = StateGraph(CodegenGraphState)
    graph.add_node("generate", _node_generate)
    graph.add_node("validate", _node_validate)
    graph.add_node("execute", _node_execute)
    graph.add_node("inspect", _node_inspect)

    graph.set_entry_point("generate")
    graph.add_conditional_edges("generate", _route_after_generate, {"validate": "validate", "end": END})
    graph.add_conditional_edges(
        "validate",
        _route_after_validate,
        {"generate": "generate", "execute": "execute", "end": END},
    )
    graph.add_conditional_edges(
        "execute",
        _route_after_execute,
        {"generate": "generate", "inspect": "inspect", "end": END},
    )
    graph.add_conditional_edges(
        "inspect",
        _route_after_inspect,
        {"generate": "generate", "end": END},
    )
    return graph.compile()


_COMPILED_GRAPH = None


def get_codegen_graph():
    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is None:
        _COMPILED_GRAPH = build_codegen_graph()
    return _COMPILED_GRAPH


def run_codegen_graph(
    record: SkillRecord,
    query: str,
    model,
    *,
    run_id: str,
    user_id: str | None = None,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    input_context: str = "",
    on_progress: ProgressCallback | None = None,
) -> CodegenLoopResult:
    ctx = CodegenGraphContext(
        record=record,
        query=query,
        model=model,
        run_id=run_id,
        user_id=user_id,
        input_context=input_context,
        max_rounds=max_rounds,
        before_snapshot=snapshot_output_files(record.path),
        started=time.time(),
        on_progress=on_progress,
    )
    graph = get_codegen_graph()
    graph.invoke(
        {"round_num": 0},
        config={"configurable": {"ctx": ctx}, "recursion_limit": max_rounds * 6 + 4},
    )
    if ctx.user_id and ctx.run_id and not ctx.loop_result.artifacts:
        for gen_rec in reversed(ctx.loop_result.rounds):
            if gen_rec.result.returncode != 0:
                continue
            artifacts = _collect_codegen_artifacts(ctx)
            if artifacts:
                ctx.loop_result.artifacts = artifacts
                ctx.loop_result.succeeded = True
                gen_rec.artifacts = artifacts
                break
    if ctx.loop_result.succeeded and not ctx.loop_result.artifacts:
        ctx.loop_result.succeeded = False
    return ctx.loop_result
