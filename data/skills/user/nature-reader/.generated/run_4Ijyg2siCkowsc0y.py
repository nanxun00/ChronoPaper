import json
import re
from pathlib import Path

# 配置路径
run_id = "4Ijyg2siCkowsc0y"
base_dir = Path.cwd()
output_dir = base_dir / "output" / "runs" / run_id
figures_dir = base_dir / "output" / "assets" / "figures"
output_dir.mkdir(parents=True, exist_ok=True)
figures_dir.mkdir(parents=True, exist_ok=True)

# 论文段落（Original / 中文对照）
paragraphs = [
    {
        "original": "Organoids are in vitro models generated through the self-organization of adult stem cells or pluripotent stem cells under three-dimensional culture conditions. They can reproduce key structural and functional features of real tissues or organs to a certain extent. Therefore, they have attracted broad attention in developmental biology, disease modeling, drug screening, and precision medicine [1–3]. Sato et al. showed that a single Lgr5+ stem cell can form intestinal organoids with crypt-villus structures in vitro, laying an important foundation for modern organoid culture systems [1]. Lancaster and Knoblich systematically summarized the potential of organoids in developmental and disease research [2], and Clevers further promoted their application in disease modeling and regenerative medicine [3]. In recent years, advances in organoid culture systems and imaging technologies have allowed researchers to acquire large numbers of microscopic images for analyzing growth status, morphological evolution, and population heterogeneity. Automated image analysis has therefore become an important tool in organoid research [4–6]. Bright-field microscopic imaging is widely used for routine organoid monitoring because it has low equipment cost, requires simple sample preparation, and supports long-term dynamic observation. However, compared with fluorescence imaging, bright-field imaging suffers from complex backgrounds, low contrast, blurred boundaries, and target adhesion. These issues substantially increase the difficulty of automatic recognition and fine-grained analysis [4–9]. Therefore, accurate, stable, and quantifiable organoid image analysis under complex bright-field conditions has become an important research topic in this field.",
        "chinese": "类器官是通过成体干细胞或多能干细胞在三维培养条件下自组织形成的体外模型，能够在一定程度上再现真实组织或器官的关键结构和功能特征，因此在发育生物学、疾病建模、药物筛选和精准医学中受到广泛关注[1–3]。Sato等人证明单个Lgr5+干细胞可在体外形成具有隐窝-绒毛结构的肠道类器官，为现代类器官培养体系奠定了重要基础[1]。Lancaster和Knoblich系统总结了类器官在发育和疾病研究中的潜力[2]，Clevers进一步推动了其在疾病建模和再生医学中的应用[3]。近年来，类器官培养体系和成像技术的进步使得研究者能够获取大量显微图像，用于分析生长状态、形态演变和群体异质性，自动化图像分析因此成为类器官研究的重要工具[4–6]。明场显微成像因其设备成本低、样本制备简单且支持长期动态观察，被广泛用于类器官的常规监测。然而，相比于荧光成像，明场成像存在背景复杂、对比度低、边界模糊以及目标粘连等问题，这些问题显著增加了自动识别与精细分析的难度[4–9]。因此，如何在复杂明场条件下实现准确、稳定且可量化的类器官图像分析，已成为该领域的重要研究课题。"
    },
    {
        "original": "In organoid image analysis, early methods such as OrganoSeg relied on traditional image processing and rule-based design for bright-field morphological measurement. These methods can provide basic indicators such as area and circularity, but their generalization ability is limited in images with complex backgrounds, irregular morphology, and dense instances [4]. With the development of deep learning, methods such as OrganoID, OrganelX, OrgaSegment, D-CryptO, and POST have introduced convolutional neural networks and instance segmentation techniques. These methods enable automated workflows from target detection and individual tracking to morphological quantification [5–9]. They have greatly improved analytical capability. In medical and microscopic image segmentation, U-Net, Mask R-CNN, and Transformer-based methods have become mainstream approaches [10–16]. MaskFormer improves global feature representation through a unified mask classification paradigm [15–16]. Mask2Former further enhances segmentation performance through masked attention [16]. TransUNet and Swin-Unet combine the local modeling ability of CNNs with the global modeling ability of Transformers and show strong performance in complex structure segmentation [17–18]. However, existing methods still face clear bottlenecks in bright-field organoid scenarios. Small targets account for a large proportion and often show weak grayscale differences from the background. This limits the ability of shallow features to represent fine-grained structures. Instances are densely distributed, boundaries are blurred, and adhesion often occurs, which makes separation more difficult. Most methods only output segmentation masks and are not directly linked to downstream morphological analysis. This limits their use in practical experiments. Therefore, a unified modeling method that considers small-object representation, dense instance separation, and quantitative analysis capability is still needed [23].",
        "chinese": "在类器官图像分析中，早期方法如OrganoSeg依赖传统图像处理和基于规则的明场形态测量，能够提供面积、圆度等基本指标，但在背景复杂、形态不规则及实例密集的图像中泛化能力有限[4]。随着深度学习的发展，OrganoID、OrganelX、OrgaSegment、D-CryptO和POST等方法引入了卷积神经网络与实例分割技术，实现了从目标检测、个体追踪到形态量化的自动化流程[5–9]，显著提升了分析能力。在医学和显微图像分割中，U-Net、Mask R-CNN以及基于Transformer的方法已成为主流[10–16]。MaskFormer通过统一的掩码分类范式改善了全局特征表示[15–16]，Mask2Former利用掩码注意力进一步提升了分割性能[16]。TransUNet和Swin-Unet结合了CNN的局部建模能力与Transformer的全局建模能力，在复杂结构分割中表现出色[17–18]。然而，现有方法在明场类器官场景下仍面临明显瓶颈：小目标占比大且与背景灰度差异弱，限制了浅层特征对细粒度结构的表示能力；实例分布密集、边界模糊且常发生粘连，增加了分离难度；多数方法仅输出分割掩码，未能直接关联下游形态分析，限制了实际实验应用。因此，仍需一种兼顾小目标表征、密集实例分离与定量分析能力的统一建模方法[23]。"
    },
    {
        "original": "To address these problems, this study proposes MorphoMask, a method for bright-field organoid instance segmentation and morphological quantitative analysis. The core bottleneck lies in insufficient high-resolution feature representation. Therefore, this study optimizes the basic model from two aspects, feature enhancement and spatial modeling. A weak-boundary dual-path enhancement module (WT-DPE) is embedded in the high-resolution feature layer. Through detail enhancement and cross-path fusion, this module strengthens the ability of shallow features to represent local textures, subtle boundaries, and small-scale targets. A spatial location alignment calibration module (SLAC) is introduced into the fused key features. This module improves the modeling accuracy of orientation-related spatial information and enhances the separation of adjacent instances. Based on high-quality segmentation results, instance-level and image-level morphological parameters are further extracted, including number, area, perimeter, minor axis length, and aspect ratio. This enables a seamless connection from pixel masks to quantitative analysis and forms an integrated automated analysis workflow.",
        "chinese": "针对上述问题，本文提出了MorphoMask——一种面向明场类器官实例分割与形态定量分析的方法。核心瓶颈在于高分辨率特征表征不足，因此本文从特征增强和空间建模两个角度优化基础模型。在高分辨率特征层中嵌入了弱边界双路径增强模块（WT-DPE），通过细节增强和跨路径融合，强化浅层特征对局部纹理、细微边界和小尺度目标的表征能力。在融合后的关键特征中引入空间位置对齐校准模块（SLAC），提升对方向相关空间信息的建模精度，增强相邻实例的分离能力。基于高质量分割结果，进一步提取实例级和图像级形态参数，包括数量、面积、周长、短轴长度和长宽比，实现从像素掩码到定量分析的无缝衔接，形成一体化的自动化分析流程。"
    },
    {
        "original": "The main contributions of this study are as follows: (1) A weak-boundary dual-path enhancement module (WT-DPE) is proposed. By jointly performing detail enhancement and cross-path fusion in the high-resolution feature layer, this module effectively strengthens the model's ability to represent small targets, subtle boundaries, and adherent regions. (2) A spatial location alignment calibration module (SLAC) is introduced into the key high-resolution feature layer. This module enhances the model's representation of spatial orientation information and the distribution patterns of adjacent instances, thereby improving instance separation accuracy in dense scenarios. (3) An integrated workflow for instance segmentation and morphological quantitative readout is constructed. It converts segmentation masks into interpretable and standardized morphological indicators, thereby improving the practical value of the method for organoid culture monitoring and automated phenotypic analysis.",
        "chinese": "本研究的主要贡献如下：（1）提出了弱边界双路径增强模块（WT-DPE），通过在高分辨率特征层联合执行细节增强与跨路径融合，有效强化模型对小目标、细微边界和粘连区域的表征能力；（2）在关键高分辨率特征层中引入空间位置对齐校准模块（SLAC），增强模型对空间方位信息和相邻实例分布模式的表征能力，从而提高密集场景下的实例分离准确率；（3）构建了实例分割与形态定量读出的一体化工作流，将分割掩码转化为可解释且标准化的形态指标，提升了方法在类器官培养监测和自动化表型分析中的实用价值。"
    }
]

# 搜索 *_mineru_* 配图
mineru_images = sorted(figures_dir.glob("*_mineru_*"))
image_refs = []
for img in mineru_images:
    rel_path = img.relative_to(base_dir)
    image_refs.append(str(rel_path))

# 构造 paper.md
paper_lines = []
paper_lines.append("# MorphoMask: Bright-Field Organoid Instance Segmentation and Morphological Quantitative Analysis")
paper_lines.append("")
paper_lines.append("## Original / 中文 对照")
paper_lines.append("")

for i, para in enumerate(paragraphs):
    paper_lines.append(f"### Paragraph {i+1}")
    paper_lines.append("")
    paper_lines.append("**Original:**")
    paper_lines.append(para["original"])
    paper_lines.append("")
    paper_lines.append("**中文:**")
    paper_lines.append(para["chinese"])
    paper_lines.append("")

if image_refs:
    paper_lines.append("## 相关配图")
    paper_lines.append("")
    for ref in image_refs:
        paper_lines.append(f"![Figure]({ref})")
        paper_lines.append("")

paper_content = "\n".join(paper_lines)

# 写入主交付文件
main_output = output_dir / "paper.md"
main_output.write_text(paper_content, encoding="utf-8")

# 可选 source_map.json
source_map = {
    "method": "文本基于用户提供的论文摘要和引言段落生成，未使用外部PDF",
    "original_source": "用户提供的论文文本（nature-reader 技能激活）",
    "run_id": run_id
}
source_map_path = output_dir / "source_map.json"
source_map_path.write_text(json.dumps(source_map, indent=2, ensure_ascii=False), encoding="utf-8")

# 可选 translation_notes.md
notes = [
    "翻译说明：",
    "- 技术术语保持与原文一致（如WT-DPE, SLAC, MorphoMask）",
    "- 引用标记 [1–23] 保留原文编号",
    "- 中文表达力求学术化、流畅，避免字对字硬译",
    "- 段落结构完整，无省略或合并",
    "- 配图引用使用相对路径，指向 output/assets/figures/ 下的 *_mineru_* 文件"
]
notes_path = output_dir / "translation_notes.md"
notes_path.write_text("\n".join(notes), encoding="utf-8")

# 打印主文件路径
print(main_output)
