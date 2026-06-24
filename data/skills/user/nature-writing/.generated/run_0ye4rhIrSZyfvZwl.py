#!/usr/bin/env python3
"""
Nature-Writing 技能 - 标注不确定性参考手册生成器

根据用户需求“标注不确定性”，本脚本生成一个结构化的 Markdown 参考手册，
帮助学术写作者准确、规范地描述研究中的不确定性，包括误差范围、局限性、假设和置信水平。
主交付文件：output/runs/0ye4rhIrSZyfvZwl/uncertainty_annotation_guide.md
"""

import pathlib
import datetime

def main():
    # 1. 定义路径
    skill_root = pathlib.Path(__file__).parent
    run_id = "0ye4rhIrSZyfvZwl"
    output_dir = skill_root / "output" / "runs" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    deliverable_path = output_dir / "uncertainty_annotation_guide.md"

    # 2. 生成文档内容
    current_date = datetime.date.today().isoformat()
    md_content = f"""---
title: "学术写作中的不确定性标注参考手册"
date: "{current_date}"
run_id: "{run_id}"
purpose: "提供规范、清晰的学术写作不确定性表述指南"
---

# 标注不确定性：学术写作参考手册

在科学写作中，明确、诚实地标注不确定性是建立研究可信度和严谨性的核心。本手册提供系统性的术语、表述模板和结构框架，以帮助研究者规范地表达数据、方法和结论中的局限性、误差范围及置信水平。

## 1. 不确定性的来源与分类

准确标注不确定性，首先需识别其主要来源。

| 来源类别 | 具体描述 | 写作关注点 |
| :--- | :--- | :--- |
| **测量与数据** | 仪器精度、采样误差、数据噪声。 | 强调可重复性和误差范围。 |
| **模型与假设** | 理论模型的简化、参数的先验假设。 | 清晰列出关键假设及其潜在影响。 |
| **统计推断** | 样本量限制、置信区间的宽窄、p值的含义。 | 区分统计显著性与实际意义。 |
| **实验条件** | 受控变量、环境因素、实验设计的固有局限。 | 说明结果的可推广性边界。 |
| **外部与系统性** | 未建模的外部因素、系统偏差。 | 讨论其对结论的潜在偏移。 |

## 2. 核心术语与定义

使用标准术语是清晰沟通的基础。

- **误差 (Error)**：测量值与真值（或约定真值）之差。分为**随机误差**（可重复测量评估）和**系统误差**（需要校准）。
- **不确定度 (Uncertainty)**：表征赋予被测量值分散性的非负参数。常用**扩展不确定度 (U)**，表示测量值以一定概率（如95%）落入该区间。
- **置信区间 (Confidence Interval, CI)**：一个区间估计，用于表示参数（如均值）的估计范围。`95% CI`意味着在重复抽样中，有95%的区间会包含总体真值。
- **p值 (p-value)**：在零假设成立的情况下，观察到当前或更极端数据的概率。**p值不是**效应大小或结果重要性的度量。
- **可信区间 (Credible Interval)**：贝叶斯统计中，表示参数后验概率分布的一个区间，其包含了特定概率质量（如95%）。
- **显著性水平 (Significance Level, α)**：在假设检验中，拒绝零假设时允许犯**第一类错误**（假阳性）的概率阈值，通常设为0.05。

## 3. 表达不确定性的句式模板

### 3.1 描述测量与统计结果

- **模板 A (均值±误差)**：
  > “The mean `[测量指标]` was `[数值]` ± `[不确定度数值]` `[单位]`。”
  > *示例：The mean particle diameter was 45.2 ± 2.1 μm.*

- **模板 B (置信区间)**：
  > “The estimated `[参数]` was `[点估计值]` (95% CI: `[下限]`, `[上限]`).”
  > *示例：The treatment effect was a reduction of 12.3% (95% CI: 8.7%, 15.9%).*

- **模板 C (p值报告)**：
  > “There was a statistically significant difference in `[指标]` between groups (F(`[自由度1]`, `[自由度2]`) = `[F值]`, p = `[p值]`, η² = `[效应量]`).”
  > *注：报告效应量（如η²， Cohen‘s d）比仅报告p值更有信息量。*

### 3.2 阐述局限性与假设

- **模板 D (直接陈述局限)**：
  > “A limitation of this study is the reliance on `[具体局限]`, which may have `[潜在影响]`. Future work should `[改进建议]`.”

- **模板 E (提出假设)**：
  > “This conclusion assumes that `[关键假设]` holds true. If this assumption is violated, the results would `[后果]`.”

- **模板 F (界定适用范围)**：
  > “Our findings are therefore applicable primarily to `[具体条件/群体]`, and may not generalize to `[其他条件/群体]`.”

### 3.3 讨论数据质量与可靠性

- **模板 G (数据可靠性)**：
  > “Data quality was assessed via `[质量控制方法，如重复测量、校准]`. The resulting measurement uncertainty was estimated at `[数值]` `[单位]`.”

- **模板 H (模型稳健性)**：
  > “The model results are sensitive to the choice of `[参数/假设]`. A sensitivity analysis demonstrated that varying this factor within plausible ranges (`[范围]`) changed the output by `[结果变化]`.”

## 4. 不同章节中的应用框架

| 论文章节 | 不确定性标注重点 | 示例表述 |
| :--- | :--- | :--- |
| **摘要** | 简要提及主要结论的核心不确定度或置信水平。 | “We find a significant correlation (r=0.72, p<0.001), though this is based on a moderate sample size.” |
| **方法** | 详细说明测量不确定度、模型假设、统计检验选择依据。 | “All instruments were calibrated daily according to ISO standard XYZ, with a certified uncertainty of ±0.5%.” |
| **结果** | 以图表（误差线、箱线图）和文字结合形式呈现数据分散性。 | “Results are presented as mean ± standard error of the mean (SEM). Error bars in Figure 2 represent the 95% confidence interval.” |
| **讨论** | 分析不确定性的来源、影响，并将其置于更广泛的背景中。 | “While the effect size is notable, the wide confidence interval suggests that further replication is needed to narrow down the true magnitude.” |
| **结论** | 基于不确定性对结论的强度进行限定。 | “Therefore, our data support, but do not definitively prove, the hypothesis that…” |

## 5. 快速参考：常用不确定度表达对照表

| 表述类型 | 适用场景 | 注意事项 |
| :--- | :--- | :--- |
| `mean ± SD` | 展示数据的**自然变异**或分布范围。 | 不直接用于推断总体参数。 |
| `mean ± SEM` | 展示样本均值作为总体均值估计的**精确度**。 | SEM通常比SD小，**不要**混淆两者。 |
| `95% CI` | 提供总体参数的**区间估计**，是报告推断结果的首选。 | 最直观地显示了估计的可靠性。 |
| `p < 0.05` | 表明结果在统计学上**显著**（相对于零假设）。 | **必须**结合效应量和置信区间一起解释。 |
| `probability = X%` | 贝叶斯框架下，陈述参数落在某区间的**主观概率**。 | 需明确说明所依据的先验信息。 |

---
*本手册由 `nature-writing` 技能根据指令“标注不确定性”自动生成，旨在提供写作参考，不替代具体领域的方法学规范。*
"""

    # 3. 写入文件
    deliverable_path.write_text(md_content, encoding="utf-8")
    print(f"✅ 不确定性标注参考手册已生成: {deliverable_path}")

if __name__ == "__main__":
    main()
