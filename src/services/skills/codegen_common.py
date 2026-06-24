"""Codegen 共享：LLM 请求、结果结构、代码提取。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from src.integrations.llm.prompts import (
    skill_codegen_revise_prompt_template,
    skill_codegen_write_prompt_template,
)
from src.services.skills.generated_runner import sanitize_run_id
from src.services.skills.pptx_quality import min_required_slides, parse_target_slide_count
from src.services.skills.registry import SkillRecord
from src.services.skills.script_runner import ScriptRunResult
from src.services.skills.toolchain import CODEGEN_ALLOWED_PACKAGES_TEXT
from src.utils.logging_config import setup_logger

logger = setup_logger("SkillCodegenCommon")

_PYTHON_FENCE_RE = re.compile(
    r"```(?:python)?\s*\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)


@dataclass
class CodegenLoopResult:
    rounds: list[Any] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    succeeded: bool = False
    last_inspection_feedback: str | None = None
    pending_approval: dict[str, Any] | None = None

    def to_run_dicts(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for idx, rec in enumerate(self.rounds, start=1):
            d = rec.to_dict()
            d["round"] = idx
            out.append(d)
        return out


def extract_python_code(text: str) -> str | None:
    raw = (text or "").strip()
    if not raw:
        return None
    blocks = _PYTHON_FENCE_RE.findall(raw)
    if blocks:
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


def _skill_extra_rules(skill_id: str, query: str, run_id: str) -> str:
    if skill_id == "nature-paper2ppt":
        target = parse_target_slide_count(query)
        minimum = min_required_slides(target)
        return f"""nature-paper2ppt 专项（必须遵守）：
- 目标 **{target} 张** 幻灯片（含标题页），不得少于 {minimum} 张
- 用 PyMuPDF 读取 PDF 全文或至少摘要+引言+方法+结果+讨论，禁止 range(min(5, len(doc)))
- 先定义 slides 列表（title + 2–4 条来自论文的中文 bullet），再循环 prs.slides.add_slide 创建
- 至少 2 张结果页；可插入 figures 目录中文件名含 mineru 的配图，禁止整页预览 PNG 全屏
- 禁止占位文案：「方法1：具体技术描述」「本文研究的主要问题和意义」等
- 保存 output/runs/{run_id}/final_presentation_cn.pptx 与 output/runs/{run_id}/qa_report.md（写明 slide 总数）"""
    if skill_id == "nature-figure":
        return f"""nature-figure 专项（必须遵守）：
- 用 matplotlib（Agg 后端）读取用户消息中的 CSV/表格字符串，解析为数据后绘制柱状图或多子图
- 输出目录：output/runs/{run_id}/，至少保存 1 张 PNG（如 model_comparison.png），dpi≥300
- 禁止只 print 路径、禁止 shutil 删除技能根目录、禁止访问技能目录外绝对路径
- 用户已给出数据时禁止生成 mock 数据"""
    if skill_id == "nature-reader":
        return f"""nature-reader 专项（必须遵守）：
- 主交付：output/runs/{run_id}/paper.md（或 TISS_net_bilingual.md），段落级 **Original / 中文** 对照
- 用 PyMuPDF 读 PDF 全文；图表必须嵌入 `output/assets/figures/` 下已列出的 *_mineru_* 配图（相对路径）
- 禁止声称无法访问图像；禁止只写占位翻译「[中文翻译待定]」
- 可选：source_map.json、translation_notes.md；保存后 print 主文件路径"""
    if skill_id == "nature-reviewer":
        return f"""nature-reviewer 专项（必须遵守）：
- 主交付：**Markdown 审稿报告**，写入 output/runs/{run_id}/reviewer_report.md
- **禁止**生成 .pptx / .docx；禁止 python-pptx、Presentation
- 用 PyMuPDF 读取已同步 PDF 全文（或摘要+方法+结果+讨论），基于论文事实撰写
- 报告须含 Markdown 标题与章节：Review setup、Reviewer 1/2/3、Cross-review synthesis、Risk / unsupported claims
- 每位 Reviewer 须覆盖：Overall assessment、Major strengths/concerns、Technical failings、Nature-style criteria、Recommendation posture
- 可选另存 output/runs/{run_id}/review_results.json（结构化摘要）；主交付仍是 .md
- 禁止占位 bullet；内容必须来自论文，不得编造实验或引用
- 保存 reviewer_report.md 后 print 其路径"""
    return ""


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
    artifact_inspection: str | None = None,
) -> str | None:
    if model is None:
        return None

    ctx_block = input_context or "（无同步文献资源）"
    safe_run = sanitize_run_id(run_id)
    extra_rules = _skill_extra_rules(record.id, query, safe_run)

    if round_num == 1:
        prompt = skill_codegen_write_prompt_template.format(
            skill_id=record.id,
            query=query,
            run_id=safe_run,
            input_context=ctx_block,
            allowed_packages=CODEGEN_ALLOWED_PACKAGES_TEXT,
            skill_extra_rules=extra_rules,
        )
    else:
        err_parts: list[str] = []
        if artifact_inspection:
            err_parts.append(artifact_inspection)
        if validation_errors:
            err_parts.append("校验错误：\n" + "\n".join(validation_errors))
        elif previous_result:
            err_parts.append(previous_result.to_context_block())
        err_text = "\n\n".join(err_parts) if err_parts else "（无详细错误）"
        prompt = skill_codegen_revise_prompt_template.format(
            skill_id=record.id,
            query=query,
            run_id=safe_run,
            round_num=round_num,
            previous_code=(previous_code or "")[:12000],
            error_context=err_text,
            input_context=ctx_block,
            allowed_packages=CODEGEN_ALLOWED_PACKAGES_TEXT,
            skill_extra_rules=extra_rules,
            artifact_inspection=artifact_inspection or "（无产物质检反馈）",
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
