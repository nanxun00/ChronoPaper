"""多轮技能代码生成：模型写代码 → 校验执行 → 根据错误修订。"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any

from src.integrations.llm.prompts import (
    skill_codegen_revise_prompt_template,
    skill_codegen_write_prompt_template,
)
from src.services.skills.artifact_collector import (
    artifacts_context_block,
    collect_skill_artifacts,
    snapshot_output_files,
)
from src.services.skills.code_validator import validate_generated_code
from src.services.skills.generated_runner import (
    GeneratedRunRecord,
    sanitize_run_id,
    should_attempt_codegen,
    write_generated_script,
    run_generated_script,
)
from src.services.skills.registry import SkillRecord
from src.services.skills.script_runner import ScriptRunResult
from src.services.skills.toolchain import CODEGEN_ALLOWED_PACKAGES_TEXT
from src.utils.logging_config import setup_logger

logger = setup_logger("SkillCodegenAgent")

_PYTHON_FENCE_RE = re.compile(
    r"```(?:python)?\s*\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)
DEFAULT_MAX_ROUNDS = 3


@dataclass
class CodegenLoopResult:
    rounds: list[GeneratedRunRecord] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    succeeded: bool = False

    def to_run_dicts(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for idx, rec in enumerate(self.rounds, start=1):
            d = rec.to_dict()
            d["round"] = idx
            out.append(d)
        return out


def extract_python_code(text: str) -> str | None:
    """从模型回复中提取 Python 代码（优先 ```python 块）。"""
    raw = (text or "").strip()
    if not raw:
        return None

    blocks = _PYTHON_FENCE_RE.findall(raw)
    if blocks:
        # 取最长代码块（通常是完整脚本）
        return max(blocks, key=len).strip()

    if "import " in raw or "from " in raw:
        return raw
    return None


def _model_text(response: Any) -> str:
    content = getattr(response, "content", None)
    if content is not None:
        return str(content)
    if isinstance(response, dict):
        return str(response.get("content", ""))
    return str(response)


def request_codegen_code(
    query: str,
    record: SkillRecord,
    model,
    *,
    run_id: str = "run",
    round_num: int = 1,
    previous_code: str | None = None,
    previous_result: ScriptRunResult | None = None,
    validation_errors: list[str] | None = None,
    input_context: str = "",
) -> str | None:
    """向模型请求一轮 Python 脚本。"""
    if model is None:
        return None

    ctx_block = input_context or "（无同步文献资源）"
    safe_run = sanitize_run_id(run_id)

    if round_num == 1:
        prompt = skill_codegen_write_prompt_template.format(
            skill_id=record.id,
            query=query,
            run_id=safe_run,
            input_context=ctx_block,
            allowed_packages=CODEGEN_ALLOWED_PACKAGES_TEXT,
        )
    else:
        err_text = ""
        if validation_errors:
            err_text = "校验错误：\n" + "\n".join(validation_errors)
        elif previous_result:
            err_text = previous_result.to_context_block()
        prompt = skill_codegen_revise_prompt_template.format(
            skill_id=record.id,
            query=query,
            run_id=safe_run,
            round_num=round_num,
            previous_code=(previous_code or "")[:12000],
            error_context=err_text or "（无详细错误）",
            input_context=ctx_block,
            allowed_packages=CODEGEN_ALLOWED_PACKAGES_TEXT,
        )

    try:
        response = model.predict(
            [
                {
                    "role": "system",
                    "content": "你是 Python 脚本生成器。只输出一个 ```python 代码块，不要其他解释。",
                },
                {"role": "user", "content": prompt},
            ],
            stream=False,
        )
        return extract_python_code(_model_text(response))
    except Exception as exc:
        logger.warning("Codegen request failed round %d for %s: %s", round_num, record.id, exc)
        return None


def run_codegen_loop(
    record: SkillRecord,
    query: str,
    model,
    *,
    run_id: str,
    user_id: str | None = None,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    input_context: str = "",
) -> CodegenLoopResult:
    """多轮：写代码 → 校验 → 执行 → 失败则修订。"""
    loop_result = CodegenLoopResult()
    before = snapshot_output_files(record.path)
    started = time.time()
    purpose = "生成技能产物"

    previous_code: str | None = None
    previous_result: ScriptRunResult | None = None
    validation_errors: list[str] | None = None

    for round_num in range(1, max_rounds + 1):
        code = request_codegen_code(
            query,
            record,
            model,
            run_id=run_id,
            round_num=round_num,
            previous_code=previous_code,
            previous_result=previous_result,
            validation_errors=validation_errors,
            input_context=input_context,
        )
        if not code:
            logger.warning("Codegen round %d: no code extracted for %s", round_num, record.id)
            break

        validation = validate_generated_code(code)
        if not validation.ok:
            logger.warning(
                "Codegen round %d validation failed for %s: %s",
                round_num,
                record.id,
                validation.errors,
            )
            gen_rec = GeneratedRunRecord(
                purpose=purpose,
                script_rel=f".generated/run_{run_id}_r{round_num}.py",
                result=ScriptRunResult(
                    script=f".generated/run_{run_id}_r{round_num}.py",
                    argv=[],
                    returncode=-1,
                    stdout="",
                    stderr="; ".join(validation.errors),
                ),
                validation_errors=validation.errors,
            )
            loop_result.rounds.append(gen_rec)
            previous_code = code
            previous_result = gen_rec.result
            validation_errors = validation.errors
            continue

        validation_errors = None
        script_path = write_generated_script(
            record.path,
            run_id,
            code,
            round_num=round_num,
        )
        result = run_generated_script(record.path, script_path)
        gen_rec = GeneratedRunRecord(
            purpose=purpose,
            script_rel=script_path.relative_to(record.path.resolve()).as_posix(),
            result=result,
        )
        loop_result.rounds.append(gen_rec)

        if result.returncode == 0 and user_id and run_id:
            artifacts = collect_skill_artifacts(
                record.path,
                before,
                user_id,
                run_id,
                since_ts=started - 2.0,
            )
            if not artifacts:
                artifacts = collect_skill_artifacts(
                    record.path,
                    {},
                    user_id,
                    run_id,
                    since_ts=started - 2.0,
                )
            if artifacts:
                gen_rec.artifacts = artifacts
                loop_result.artifacts = artifacts
                loop_result.succeeded = True
                logger.info(
                    "Codegen succeeded round %d for %s, %d artifacts",
                    round_num,
                    record.id,
                    len(artifacts),
                )
                break

        previous_code = code
        previous_result = result
        logger.info(
            "Codegen round %d finished rc=%s for %s, retrying",
            round_num,
            result.returncode,
            record.id,
        )

    return loop_result


def codegen_loop_context_block(loop: CodegenLoopResult) -> str:
    """合并多轮执行结果，注入主对话 system。"""
    if not loop.rounds:
        return ""

    lines = [
        "## 技能多轮代码执行（ChronoPaper 平台）",
        f"共 {len(loop.rounds)} 轮；成功：{'是' if loop.succeeded else '否'}。",
        "以下脚本已由服务端校验并执行，请据此回答用户。",
    ]

    if loop.succeeded:
        lines.append(
            "**文件已生成**——在回复中说明产物名称与下载方式，不要声称「环境无法生成 pptx/文件」。"
        )
    else:
        lines.append("全部轮次未产出文件，请根据最后一轮错误说明原因，勿编造已成功。")

    for idx, rec in enumerate(loop.rounds, start=1):
        lines.append(f"\n### 第 {idx} 轮")
        if rec.validation_errors:
            lines.append("校验失败：" + "; ".join(rec.validation_errors))
        else:
            lines.append(rec.result.to_context_block())

    if loop.artifacts:
        block = artifacts_context_block(loop.artifacts)
        if block:
            lines.append("\n" + block)

    return "\n".join(lines)


def maybe_run_codegen_loop(
    query: str,
    record: SkillRecord,
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

    context = codegen_loop_context_block(loop)
    return context, loop.to_run_dicts()
