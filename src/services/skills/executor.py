"""Skill 执行：路由 + 加载上下文，注入 system prompt。"""
from __future__ import annotations

from typing import Any

from src.services.skills.loader import load_skill_context
from src.services.skills.registry import get_skill_registry
from src.services.skills.router import resolve_skill_id
from src.services.skills.generated_runner import _FILE_OUTPUT_SKILLS
from src.services.skills.input_sync import (
    collect_paper_ids_from_meta,
    sync_literature_to_skill,
)
from src.services.skills.codegen_progress import ProgressCallback
from src.services.skills.script_planner import maybe_run_skill_scripts
from src.utils.logging_config import setup_logger

logger = setup_logger("SkillExecutor")

_SYSTEM_WRAPPER = """你是 ChronoPaper 科研助手。请严格遵循以下技能指令完成用户任务。
若技能指令与通用常识冲突，以技能指令为准；不得编造未给出的实验数据或引用。

{skill_context}
"""

_PLATFORM_NOTE = """## ChronoPaper 平台说明
本环境在对话前通过 **LangGraph 编排**执行技能脚本：写代码 → 静态校验 → 运行 → **解析真实产物**（页数/字数/结构）→ 未达标自动修订（最多 3 轮）。
- 若脚本含删除目录等高危操作，会先 **LLM 安全审查**，再请你在前端确认是否放行。
- 下方「技能多轮代码执行」含**产物质检摘要**（Agent 已读取生成文件，非仅看 stdout）。
- 若显示成功且通过质检：**文件已生成**，请直接告知下载方式，勿称「环境无法生成 pptx/文件」或只贴示例代码。
- 若质检未达标，如实说明缺口（如页数不足、内容过短），勿按对话规划谎称已完成。
- **勿在回复正文粘贴完整生成脚本**；正文只说明结果与产物即可。
- **禁止**在面向用户的回复中列出 manifest.yaml、contract.md、stance.md 或技能目录绝对路径；那是内部路由，不是交付物。
"""

_SKILL_PLATFORM_OVERRIDES: dict[str, str] = {
    "nature-paper2ppt": """## ChronoPaper × nature-paper2ppt（覆盖 SKILL 路由器）
- 主路径：后台 codegen 生成 `output/runs/{run_id}/final_presentation_cn.pptx`。
- **保底路径**：codegen 失败时平台会自动用 `scripts/build_pptx.py` + JSON 大纲再试一次。
- **仅当**下方「技能生成的文件」含 `.pptx` 时，才可提示点击下载；文件名以 chip 为准（通常为 `final_presentation_cn.pptx`）。
- 若下方无 `.pptx` chip：如实说明失败，**禁止**虚构 MorphoMask_IEEE_Presentation.pptx 等路径或 12 页结构表。
""",
    "nature-figure": """## ChronoPaper × nature-figure（覆盖 SKILL 路由器）
- manifest / contract / stance 已由服务端注入；需要更深层 reference 时用 **read 工具**（相对路径），勿向用户展示绝对路径。
- 本平台固定用 **Python + matplotlib** 在后台写脚本出图；**不要**问「Python 还是 R？」。
- 用户消息里的 CSV/表格/指标数据 → 后台 codegen 解析并保存 PNG 到 `output/runs/{run_id}/`。
- 你的最终回复须：说明生成了哪些图、关键对比结论、如何下载；若下方无成功记录则说明失败原因。
""",
    "nature-academic-search": """## ChronoPaper × nature-academic-search（覆盖 MCP 路由）
- **未挂载 MCP 服务器**；但 `scripts/format-converter.py` 与 `scripts/academic_search.py` 可由平台**自动执行**（stdlib + 公网 API）。
- 用户要下载/导出 RIS、BibTeX、nbib 时：**禁止**说「格式转换脚本不可用」；若下方有「技能脚本执行结果」且成功，说明已生成文件并提示消息下方下载。
- 若本轮未跑脚本（例如用户只说「下载论文」但未指明 DOI）：请追问 DOI/PMID，或请用户粘贴要导出的标识；**不要**假装已下载。
- format-converter 示例：`--doi 10.xxxx/yyyy --format ris`（输出到 references/）。
""",
    "nature-citation": """## ChronoPaper × nature-citation（覆盖 SKILL 路由器）
- **禁止** LLM 临时写 Python；平台固定调用 `scripts/nature_citation.py` 做分段检索与引用导出（禁止 codegen 替代）。
- 用户粘贴引言/正文时：脚本自动分段搜索 Crossref 并导出 RIS/ENW 等到 `output/runs/{run_id}/`。
- **仅当**下方「技能生成的文件」列表中出现 `.ris` / `.enw` / `.rdf` 时，才可提示点击下载；**禁止**编造路径（如 `/用户目录/...`）。
- 若下方无引用导出文件：如实说明检索未产出或输入过短，**勿谎称**已生成 RIS。
- 纯 DOI 批量导出仍走 `nature-academic-search` 包内 `format-converter.py`（`.bib`/`.ris`/`.nbib`）。
""",
    "nature-reader": """## ChronoPaper × nature-reader（覆盖 SKILL 路由器）
- 引用文献的 PDF 与 **MinerU 解析配图** 已在对话前同步到技能目录（见「已同步文献资源」中的 `output/assets/figures/*_mineru_*`）。
- 后台 Python 脚本会生成 `output/runs/{run_id}/` 下的 `.md` 阅读稿，并嵌入 MinerU 图表链接。
- **禁止**称「无法提取 PDF 图像 / 当前环境看不到图 / 需手动从 PDF 截图」。
- **禁止**在聊天正文粘贴整篇 bilingual Markdown（可简要概括结构 + 1–2 段示例）；完整稿请让用户在消息下方**下载 .md 文件**。
- 若「技能多轮代码执行」显示成功或下方有「技能生成的文件」：直接说明文件名、章节覆盖与下载方式，勿忽略已有产物自行重写全文。
""",
    "nature-reviewer": """## ChronoPaper × nature-reviewer（覆盖 SKILL 路由器）
- 本平台通过后台 Python 生成 **Markdown 审稿报告**（`output/runs/{run_id}/reviewer_report.md`），不是 PPT。
- 报告结构须对齐 SKILL：Review setup + 3 位 Reviewer + Cross-review synthesis + Risk / unsupported claims。
- **禁止**生成 .pptx；**禁止**在聊天正文粘贴完整三份审稿意见（可概括共识与主要风险）。
- 若下方有成功产物：说明报告文件名、主要结论与下载方式；勿忽略已有 .md 自行重写。
""",
}


def _platform_skill_override(skill_id: str) -> str:
    return _SKILL_PLATFORM_OVERRIDES.get(skill_id, "")


def _artifacts_contain_suffix(artifacts: list[dict[str, Any]], suffix: str) -> bool:
    suffix = suffix.lower()
    for item in artifacts:
        name = str(item.get("name") or item.get("path") or "").lower()
        if name.endswith(suffix):
            return True
    return False


def _append_missing_deliverable_notice(
    system: str,
    skill_id: str,
    artifacts: list[dict[str, Any]],
) -> str:
    if skill_id == "nature-paper2ppt" and not _artifacts_contain_suffix(artifacts, ".pptx"):
        return (
            f"{system}\n\n## 产物状态（必读）\n"
            "本轮**未**收集到 `final_presentation_cn.pptx` 下载文件。"
            "请向用户如实说明 PPT 尚未生成或生成失败，并根据「技能多轮代码执行」中的错误/质检信息给出原因；"
            "**禁止**虚构幻灯片目录或下载链接。"
        )
    return system


def _chat_final_role(skill_id: str) -> str:
    from src.services.skills.agent.prompts import SKILL_AGENT_TOOLS_PROMPT

    lines = [
        "## 【最高优先级】面向用户的最终回复规则",
        "- 需要读技能 reference 时，在推理阶段使用 read 工具；**给用户的最终回复**必须是中文说明，不含 `<function=...>` 或绝对路径",
        "- **禁止**在最终回复中输出 manifest.yaml、contract.md 等内部路由路径",
    ]
    if skill_id in _FILE_OUTPUT_SKILLS:
        lines.extend(
            [
                "- 若下方有「技能多轮代码执行」且成功：说明已生成的图表/文件、主要对比结论，提示用户点击消息下方下载",
                "- 若无成功记录：如实说后台生成失败，建议重试",
            ]
        )
        if skill_id == "nature-reader":
            lines.append(
                "- nature-reader：勿在回复中贴整篇对照 Markdown；只概括结构并引导下载 .md"
            )
        if skill_id == "nature-reviewer":
            lines.append(
                "- nature-reviewer：勿在回复中贴完整三份审稿意见；引导下载 reviewer_report.md，勿称已生成 PPT"
            )
    return "\n".join(lines) + "\n\n" + SKILL_AGENT_TOOLS_PROMPT


def prepare_skill_turn(
    query: str,
    meta: dict,
    *,
    model=None,
    user_id: str | None = None,
    run_id: str | None = None,
    on_progress: ProgressCallback | None = None,
    script_context: str = "",
) -> tuple[str | None, dict[str, Any]]:
    """
    解析并加载技能，返回 (system_prompt, skill_info)。
    skill_info 写入 refs / meta 供前端展示。
    """
    registry = get_skill_registry()
    skill_id, route_mode = resolve_skill_id(
        query,
        meta,
        registry.list_all(),
        model=model,
    )
    if not skill_id:
        return None, {"skill_mode": route_mode, "skill_id": None, "skill_name": None}

    record = registry.get(skill_id)
    if not record or not record.enabled:
        return None, {"skill_mode": route_mode, "skill_id": None, "skill_name": None}

    try:
        ctx = load_skill_context(record)
    except Exception as exc:
        logger.warning("Load skill %s failed: %s", skill_id, exc)
        return None, {"skill_mode": route_mode, "skill_id": skill_id, "skill_error": str(exc)}

    script_ctx = None
    script_runs: list = []
    pending_approval: dict | None = None
    run_scripts = meta.get("skill_run_scripts", True) is not False
    allow_codegen = meta.get("skill_codegen", True) is not False

    input_context = ""
    skill_inputs: dict[str, Any] = {}
    approval_id = meta.get("codegen_approval_id")
    if approval_id and user_id:
        from src.services.skills.codegen_approval import consume_completed_approval

        completed = consume_completed_approval(str(approval_id), user_id)
        if completed:
            script_ctx = completed.context_block
            script_runs = completed.runs
            allow_codegen = False
            run_scripts = False
        else:
            logger.warning("Codegen approval %s not found or expired", approval_id)

    if (run_scripts or allow_codegen) and script_ctx is None:
        paper_ids = collect_paper_ids_from_meta(meta)
        if paper_ids:
            synced = sync_literature_to_skill(record.path, paper_ids)
            input_context = synced.to_prompt_block()
            skill_inputs = {
                "paper_ids": synced.paper_ids,
                "pdf_paths": synced.pdf_rels,
                "figure_paths": synced.figure_rels,
            }

    if (run_scripts or allow_codegen) and script_ctx is None:
        script_ctx, script_runs, pending_approval = maybe_run_skill_scripts(
            query,
            record,
            model,
            enabled=run_scripts or allow_codegen,
            allow_codegen=allow_codegen,
            user_id=user_id,
            run_id=run_id,
            input_context=input_context,
            on_progress=on_progress,
            script_context=script_context,
        )

    system = _SYSTEM_WRAPPER.format(skill_context=ctx)
    if skill_id in _FILE_OUTPUT_SKILLS or allow_codegen:
        system = f"{system}\n\n{_PLATFORM_NOTE}"
        override = _platform_skill_override(skill_id)
        if override:
            system = f"{system}\n\n{override}"
    elif skill_id in ("nature-academic-search", "nature-citation"):
        override = _platform_skill_override(skill_id)
        if override:
            system = f"{system}\n\n{override}"
    if script_ctx:
        system = f"{system}\n\n{script_ctx}"
    elif skill_id in _FILE_OUTPUT_SKILLS and allow_codegen and not pending_approval:
        system = (
            f"{system}\n\n## 后台脚本状态\n"
            "本轮未注入执行结果（可能尚未跑完或全部失败）。"
            "请如实告知用户图表/文件尚未生成，建议重试；**禁止**输出技能 manifest/contract 路径充数。"
        )

    artifacts_for_notice: list[dict[str, Any]] = []
    if script_runs:
        for run in script_runs:
            artifacts_for_notice.extend(run.get("artifacts") or [])
    system = _append_missing_deliverable_notice(system, skill_id, artifacts_for_notice)

    if skill_id in _FILE_OUTPUT_SKILLS or allow_codegen:
        system = f"{system}\n\n{_chat_final_role(skill_id)}"

    info = {
        "skill_mode": route_mode,
        "skill_id": skill_id,
        "skill_name": record.name,
        "skill_source": record.source,
    }
    if script_runs:
        info["skill_scripts"] = script_runs
        artifacts: list[dict[str, Any]] = []
        for run in script_runs:
            artifacts.extend(run.get("artifacts") or [])
        if artifacts:
            info["artifacts"] = artifacts
    if pending_approval:
        info["codegen_pending_approval"] = pending_approval
    if skill_inputs:
        info["skill_inputs"] = skill_inputs
    logger.debug("Skill active: %s route=%s", skill_id, route_mode)
    return system, info
