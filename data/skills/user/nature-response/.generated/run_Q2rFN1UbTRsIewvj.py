#!/usr/bin/env python3
"""生成审稿意见回复模板（点对点回复格式）"""

from pathlib import Path

# 工作目录 & 输出目录
WORK_DIR = Path.cwd()
RUN_ID = "Q2rFN1UbTRsIewvj"
OUTPUT_DIR = WORK_DIR / "output" / "runs" / RUN_ID
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ===== 审稿意见结构化内容 =====
review_points = {
    "Novelty and Research Contribution (Core Problem)": [
        "1. The authors did not clearly sort out the research gaps of existing work in the introduction section. The difference between the proposed method and the latest SOTA methods in recent two years is not quantitatively and qualitatively reflected, and the core innovation points of this paper are vague and scattered throughout the full text without centralized summary.",
        "2. The research motivation is insufficient. The paper only briefly describes the defects of traditional schemes, but lacks detailed data and case analysis to prove the practical pain points of existing technologies in real application scenarios.",
        "3. In the discussion section, the authors fail to objectively analyze the limitations of the proposed method, and there is no targeted outlook for subsequent follow-up research."
    ],
    "Experimental Design and Result Verification": [
        "1. The dataset used in the experiment is single, only one public dataset is adopted, and there is no cross-dataset generalization test on multiple standard datasets in this field. The robustness of the model cannot be fully proved.",
        "2. Complete ablation experiments are missing. The effectiveness of each core module of the proposed model is not verified by group control experiments, and it is impossible to judge which module brings performance improvement.",
        "3. The comparison experiment setting is incomplete. Some mainstream classic baseline models and the latest top conference algorithms are not included in the comparison, and the performance advantage of the proposed method is not fully reflected.",
        "4. There is a lack of statistical significance analysis of experimental indicators. All experimental results only give single group data without repeated test mean and variance comparison, and the reliability of the experimental conclusion is insufficient.",
        "5. No real scene case test is provided. All experiments are limited to offline simulation data, lacking practical application value verification."
    ],
    "Logical Argumentation and Theoretical Derivation": [
        "1. Part of the theoretical formula derivation skips key intermediate steps, some symbol definitions are not uniformly marked, and the readers cannot reproduce the derivation process according to the content of the paper.",
        "2. The correlation between each chapter is weak. The connection between theoretical part, model structure and experimental part is not smooth, and the overall logical context of the article is confusing.",
        "3. Some core hypotheses of the model are not explained in detail, and the applicable scope and preconditions of the method are not clearly defined."
    ],
    "Figures, Tables and Format Standardization": [
        "1. The chart production is not standardized: the coordinate labels, legend fonts and color matching of all figures are inconsistent; the table line types, decimal retention digits of indicators are not unified; many pictures lack clear caption descriptions to explain the core information displayed.",
        "2. Some pictures are blurred, the curve overlap is serious, and it is difficult to distinguish the comparison results of different models.",
        "3. The unit of partial experimental parameters is missing, and the parameter setting description in the experimental section is too brief to reproduce the experiment."
    ],
    "Writing, Grammar and References": [
        "1. There are a large number of grammatical errors, sentence redundancy and awkward Chinglish expressions in the full text, and many professional nouns are used non-standardly. It is suggested to polish the whole manuscript by professional English editing.",
        "2. The literature sorting is outdated: nearly 40% of the cited references are papers published before 2020, and a large number of latest high-level related studies in recent three years are not cited.",
        "3. The reference format is not uniform, some journal papers lack volume, issue and page numbers, and the citation marks in the text are disordered.",
        "4. The abstract and conclusion are highly repetitive, and the abstract fails to concisely extract the core methods, key indicators and main conclusions of the paper."
    ],
    "Minor Issues": [
        "1. The abbreviations that appear for the first time in the text are not marked with full English names.",
        "2. The chapter numbering hierarchy is confused, and the subsection naming is not concise and standardized.",
        "3. Individual numerical values in the text are inconsistent with the data displayed in the table, and there are data conflicts."
    ]
}

# ===== 生成 Markdown 点对点回复模板 =====
def generate_response_md(sections: dict) -> str:
    lines = []
    lines.append("# Point-by-Point Response to Reviewer Comments\n")
    lines.append(f"**Manuscript Title:** [Fill in your paper title]\n")
    lines.append(f"**Manuscript ID:** [Manuscript Number]\n")
    lines.append("---\n")
    lines.append("## Response to Reviewer\n")
    lines.append(
        "Dear Reviewer,\n\n"
        "Thank you very much for your thorough review and constructive comments. "
        "We have carefully considered each point and revised the manuscript accordingly. "
        "Below we provide a point-by-point response. The corresponding revisions have been "
        "highlighted in the revised manuscript (in red/blue color).\n"
    )
    lines.append("---\n")

    for section_title, comments in sections.items():
        lines.append(f"## {section_title}\n")
        for i, comment in enumerate(comments, 1):
            lines.append(f"### Comment {i}\n")
            lines.append(f"**Reviewer's Comment:** {comment}\n")
            lines.append("**Author's Response:**\n\n")
            lines.append("[Provide your detailed response here. "
                         "Explain how you addressed the comment, "
                         "refer to specific sections/figures/tables in the revised manuscript.]\n")
            lines.append(f"**Revision in Manuscript:** [Location/change summary]\n")
            lines.append("\n---\n")
        lines.append("\n")

    lines.append("## References (if any new references added)\n")
    lines.append("1. [New reference 1]\n")
    lines.append("2. [New reference 2]\n\n")
    lines.append("---\n")
    lines.append("## Additional Materials\n")
    lines.append("[If supplementary materials are provided, list them here.]\n")
    return "\n".join(lines)

# ===== 写入主交付文件 =====
output_text = generate_response_md(review_points)
output_path = OUTPUT_DIR / "point_by_point_response.md"
output_path.write_text(output_text, encoding="utf-8")

print(f"✅ 点对点回复模板已生成: {output_path}")
