"""多轮技能代码生成：LangGraph 编排 + 产物质检闭环。"""
from __future__ import annotations

from typing import Any

from src.services.skills.artifact_collector import artifacts_context_block
from src.services.skills.codegen_common import CodegenLoopResult, extract_python_code
from src.services.skills.codegen_graph import DEFAULT_MAX_ROUNDS, run_codegen_graph
from src.services.skills.generated_runner import should_attempt_codegen
from src.utils.logging_config import setup_logger

logger = setup_logger("SkillCodegenAgent")

# 兼容旧 import
__all__ = [
    "CodegenLoopResult",
    "DEFAULT_MAX_ROUNDS",
    "extract_python_code",
    "run_codegen_loop",
    "codegen_loop_context_block",
    "maybe_run_codegen_loop",
]


def run_codegen_loop(
    record,
    query: str,
    model,
    *,
    run_id: str,
    user_id: str | None = None,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    input_context: str = "",
) -> CodegenLoopResult:
    """LangGraph：写代码 → 静态校验 → 执行 → 解析产物 → 未达标再改。"""
    return run_codegen_graph(
        record,
        query,
        model,
        run_id=run_id,
        user_id=user_id,
        max_rounds=max_rounds,
        input_context=input_context,
    )


def codegen_loop_context_block(loop: CodegenLoopResult) -> str:
    if not loop.rounds:
        return ""

    lines = [
        "## 技能多轮代码执行（LangGraph + 产物质检）",
        f"共 {len(loop.rounds)} 轮；成功：{'是' if loop.succeeded else '否'}。",
        "脚本已由服务端执行；下方含**真实产物解析摘要**（页数/字数/章节等），请据此回答用户。",
    ]

    if loop.succeeded:
        lines.append(
            "**文件已生成且通过产物质检**——说明产物名称与下载方式，勿声称「环境无法生成文件」。"
        )
    elif loop.last_inspection_feedback:
        lines.append("最后一轮产物质检未达标，请如实说明不足与可下载的半成品（如有）。")
    else:
        lines.append("全部轮次未产出合格文件，请根据最后一轮错误说明原因，勿编造已成功。")

    for idx, rec in enumerate(loop.rounds, start=1):
        lines.append(f"\n### 第 {idx} 轮")
        if rec.inspection_summary:
            lines.append(rec.inspection_summary)
        elif rec.validation_errors:
            lines.append("校验/质检失败：" + "; ".join(rec.validation_errors))
        else:
            lines.append(rec.result.to_context_block())

    if loop.artifacts:
        block = artifacts_context_block(loop.artifacts)
        if block:
            lines.append("\n" + block)

    return "\n".join(lines)


def maybe_run_codegen_loop(
    query: str,
    record,
    model,
    *,
    user_id: str | None = None,
    run_id: str | None = None,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    input_context: str = "",
) -> tuple[str | None, list[dict[str, Any]]]:
    if not should_attempt_codegen(query, record, builtin_ran=False):
        return None, []
    if not run_id:
        logger.warning("Codegen loop skipped: missing run_id")
        return None, []

    loop = run_codegen_loop(
        record,
        query,
        model,
        run_id=run_id,
        user_id=user_id,
        max_rounds=max_rounds,
        input_context=input_context,
    )
    if not loop.rounds:
        return None, []

    return codegen_loop_context_block(loop), loop.to_run_dicts()
