"""LLM 审查静态校验拦截的高危生成代码。"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from src.utils.logging_config import setup_logger

logger = setup_logger("SkillCodeSecurityReview")

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

_REVIEW_PROMPT = """你是 ChronoPaper 技能脚本安全审查员。生成脚本将在**技能工作目录**内以 subprocess 运行（cwd=技能根目录），不能访问目录外路径。

用户任务：{query}
技能 ID：{skill_id}

静态规则已拦截以下**高危操作**（需你判断是否可在受控目录内放行）：
{errors_block}

脚本片段（前 8000 字符）：
```python
{code_preview}
```

审查标准：
- **可放行**：仅在 output/runs/ 或临时子目录内清理/写入；matplotlib 缓存；无 subprocess/网络/越界路径
- **不可放行**：subprocess、eval/exec、删除 references/figures/SKILL.md、访问技能目录外路径、可疑混淆

只返回 JSON，不要 markdown：
{{"approved": true/false, "summary": "一句话结论", "risks": ["风险1", "风险2"]}}
"""


@dataclass
class SecurityReviewResult:
    approved: bool
    summary: str
    risks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "approved": self.approved,
            "summary": self.summary,
            "risks": self.risks,
        }


def _model_text(response: Any) -> str:
    content = getattr(response, "content", None)
    if content is not None:
        return str(content)
    if isinstance(response, dict):
        return str(response.get("content", ""))
    return str(response)


def _parse_review_json(text: str) -> SecurityReviewResult | None:
    raw = (text or "").strip()
    match = _JSON_RE.search(raw)
    if match:
        raw = match.group(0)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    approved = bool(data.get("approved"))
    summary = str(data.get("summary") or "").strip() or ("审查通过" if approved else "审查未通过")
    risks_raw = data.get("risks") or []
    risks = [str(r) for r in risks_raw] if isinstance(risks_raw, list) else []
    return SecurityReviewResult(approved=approved, summary=summary, risks=risks)


def review_generated_code_security(
    code: str,
    reviewable_errors: list[str],
    model,
    *,
    skill_id: str,
    query: str = "",
) -> SecurityReviewResult:
    """LLM 审查可放行的高危静态拦截项。无模型时保守拒绝。"""
    if model is None:
        return SecurityReviewResult(
            approved=False,
            summary="无可用模型，无法完成安全审查",
            risks=["缺少 LLM 审查"],
        )

    errors_block = "\n".join(f"- {e}" for e in reviewable_errors) or "- （无）"
    prompt = _REVIEW_PROMPT.format(
        query=(query or "")[:2000],
        skill_id=skill_id,
        errors_block=errors_block,
        code_preview=(code or "")[:8000],
    )
    try:
        response = model.predict(
            [
                {"role": "system", "content": "你只输出 JSON，不要解释或 markdown。"},
                {"role": "user", "content": prompt},
            ],
            stream=False,
        )
        parsed = _parse_review_json(_model_text(response))
        if parsed is not None:
            return parsed
    except Exception as exc:
        logger.warning("Security review LLM failed for %s: %s", skill_id, exc)

    return SecurityReviewResult(
        approved=False,
        summary="安全审查结果无法解析，已保守拒绝",
        risks=["LLM 审查输出无效"],
    )
