"""技能产物质检结果模型。"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ArtifactInspectionResult:
    """单个文件的解析摘要 + 问题列表。"""

    path: str
    kind: str
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    summary_lines: list[str] = field(default_factory=list)

    def to_feedback_lines(self) -> list[str]:
        lines = [f"### 产物 `{self.path}` ({self.kind})"]
        if self.summary_lines:
            lines.append("解析摘要：")
            lines.extend(f"- {line}" for line in self.summary_lines)
        if self.errors:
            lines.append("问题：")
            lines.extend(f"- {err}" for err in self.errors)
        if self.warnings:
            lines.append("警告：")
            lines.extend(f"- {warn}" for warn in self.warnings)
        return lines


@dataclass
class SkillInspectionReport:
    """一轮脚本执行后的产物质检报告。"""

    skill_id: str
    run_id: str
    ok: bool
    results: list[ArtifactInspectionResult] = field(default_factory=list)
    missing_deliverables: list[str] = field(default_factory=list)

    @property
    def errors(self) -> list[str]:
        out = list(self.missing_deliverables)
        for item in self.results:
            out.extend(item.errors)
        return out

    @property
    def warnings(self) -> list[str]:
        out: list[str] = []
        for item in self.results:
            out.extend(item.warnings)
        return out

    def to_feedback_block(self) -> str:
        """供 codegen 修订 prompt 与主对话 system 使用。"""
        if self.ok and not self.warnings:
            lines = ["## 产物质检（已通过）"]
            for item in self.results:
                if item.summary_lines:
                    lines.append(f"- `{item.path}`：" + "；".join(item.summary_lines[:4]))
            return "\n".join(lines)

        lines = ["## 产物质检（未达标，必须修订脚本后重试）"]
        if self.missing_deliverables:
            lines.append("缺失交付物：")
            lines.extend(f"- {p}" for p in self.missing_deliverables)
        for item in self.results:
            lines.extend(item.to_feedback_lines())
        return "\n".join(lines)
