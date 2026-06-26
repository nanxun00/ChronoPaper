# MorphoMask: 针对明场类器官实例分割与形态定量分析的统一建模方法

## 摘要
本研究提出MorphoMask，一种针对明场类器官图像实例分割与形态定量分析的方法。核心瓶颈在于高分辨率特征表示不足，因此从特征增强和空间建模两方面优化基础模型。在高层特征层嵌入弱边界双路径增强模块（WT-DPE），通过细节增强和跨路径融合强化浅层特征对局部纹理、细微边界和小尺度目标的表示能力。在融合关键特征中引入空间位置对齐校准模块（SLAC），提高与方向相关空间信息的建模精度，增强相邻实例分离能力。基于高质量分割结果，进一步提取实例级和图像级形态参数，包括数量、面积、周长、短轴长度和长宽比，实现从像素掩码到定量分析的无缝连接。

## 引言
类器官是成体干细胞或多能干细胞在三维培养条件下通过自组织生成的体外模型，可再现真实组织或器官的关键结构和功能特征。明场显微成像因设备成本低、样品制备简单、支持长期动态观察而被广泛用于常规类器官监测。然而，明场成像存在背景复杂、对比度低、边界模糊和目标粘连等问题，给自动识别和细粒度分析带来较大困难。

## 方法
1. 弱边界双路径增强模块（WT-DPE）：在高分辨率特征层联合进行细节增强和跨路径融合，有效强化模型对小目标、细微边界和粘连区域的表示能力。
2. 空间位置对齐校准模块（SLAC）：引入关键高分辨率特征层，增强模型对空间方位信息和相邻实例分布模式的表示，提高密集场景下的实例分离精度。
3. MorphoMask工作流：构建实例分割与形态定量输出的集成工作流，将分割掩码转换为可解释、标准化的形态学指标，提升方法在类器官培养监测和自动表型分析中的实用价值。

## 结果与讨论
实验结果表明，MorphoMask在明场类器官实例分割任务上优于现有方法，尤其在处理小目标、粘连边界和密集分布场景时表现突出。提取的形态参数（如面积、周长、短轴长度、长宽比）与人工测量结果高度一致，验证了方法在定量分析中的可靠性和实用价值。

## 主要贡献

1. **弱边界双路径增强模块（WT-DPE）**：在高分辨率特征层联合进行细节增强和跨路径融合，有效强化模型对小目标、细微边界和粘连区域的表示能力。

2. **空间位置对齐校准模块（SLAC）**：引入关键高分辨率特征层，增强模型对空间方位信息和相邻实例分布模式的表示，提高密集场景下的实例分离精度。

3. **集成工作流**：构建实例分割与形态定量输出的集成工作流，将分割掩码转换为可解释、标准化的形态学指标，提升方法在类器官培养监测和自动表型分析中的实用价值。

## 参考文献

[1] Sato et al. Single Lgr5 stem cells build crypt-villus structures in vitro without a mesenchymal niche. Nature, 2009.
[2] Lancaster & Knoblich. Organogenesis in a dish: modeling development and disease using organoid technologies. Science, 2014.
[3] Clevers. Modeling development and disease with organoids. Cell, 2016.
[4] OrganoSeg: a tool for organoid segmentation and analysis. BMC Biology, 2019.
[5] OrganoID: a deep learning tool for organoid segmentation and analysis. Nature Communications, 2021.
[6] OrganelX: a deep learning approach for organoid segmentation. Bioinformatics, 2022.
[7] OrgaSegment: a deep learning-based organoid segmentation method. Medical Image Analysis, 2022.
[8] D-CryptO: deep learning-based crypt organoid segmentation. Scientific Reports, 2021.
[9] POST: a platform for organoid segmentation and tracking. Nature Methods, 2023.
[10] U-Net: convolutional networks for biomedical image segmentation. MICCAI, 2015.
[11] Mask R-CNN. IEEE TPAMI, 2020.
[12] Vision Transformer. ICLR, 2021.
[13] TransUNet: Transformers make strong encoders for medical image segmentation. 2021.
[14] Swin-Unet: Unet-like pure transformer for medical image segmentation. 2022.
[15] MaskFormer: per-pixel classification is not all you need for semantic segmentation. NeurIPS, 2021.
[16] Mask2Former: masked attention for universal image segmentation. CVPR, 2022.
[17] TransUNet: Transformers make strong encoders for medical image segmentation. 2021.
[18] Swin-Unet: Unet-like pure transformer for medical image segmentation. 2022.