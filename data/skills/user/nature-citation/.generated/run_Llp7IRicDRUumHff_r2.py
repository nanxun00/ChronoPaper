#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
from pathlib import Path

# Define run ID and working directories
RUN_ID = "Llp7IRicDRUumHff"
WORK_DIR = Path.cwd()
OUTPUT_DIR = WORK_DIR / "output" / "runs" / RUN_ID
REFERENCES_DIR = WORK_DIR / "references" / "runs" / RUN_ID

# Create output directories
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
REFERENCES_DIR.mkdir(parents=True, exist_ok=True)

# ========= Context: Extract key information from the user prompt =========
# The prompt describes a research paper about MorphoMask for organoid image analysis.
# We'll generate a structured markdown summary of the paper.

paper_summary = {
    "title": "MorphoMask: Bright-Field Organoid Instance Segmentation and Morphological Quantitative Analysis",
    "authors": "Not explicitly stated in prompt (assume authors unnamed)",
    "abstract": (
        "Organoids are in vitro models that reproduce key features of real tissues. "
        "Bright-field imaging is widely used but suffers from complex backgrounds and blurred boundaries. "
        "Existing deep learning methods face bottlenecks with small targets, dense instances, and limited quantitative analysis. "
        "MorphoMask addresses these issues via a weak-boundary dual-path enhancement module (WT-DPE) "
        "and a spatial location alignment calibration module (SLAC), enabling accurate instance segmentation "
        "and seamless morphological quantification."
    ),
    "introduction": {
        "background": (
            "Organoids are generated from adult or pluripotent stem cells under 3D culture. "
            "They attract broad attention in developmental biology, disease modeling, drug screening, and precision medicine [1-3]. "
            "Sato et al. showed single Lgr5+ stem cells form intestinal organoids [1]. "
            "Lancaster and Knoblich summarized organoid potential [2]; Clevers promoted applications [3]."
        ),
        "problem": (
            "Bright-field imaging has low equipment cost and supports long-term observation, but suffers from complex backgrounds, "
            "low contrast, blurred boundaries, and target adhesion [4-9]. "
            "This makes automatic recognition difficult."
        ),
        "methods_overview": (
            "Early methods (OrganoSeg [4]) rely on traditional image processing with limited generalization. "
            "Deep learning methods (OrganoID, OrganelX, OrgaSegment, D-CryptO, POST [5-9]) improve analysis. "
            "U-Net, Mask R-CNN, Transformer methods [10-16] are mainstream. "
            "MaskFormer, Mask2Former [15-16] use unified mask classification. "
            "TransUNet, Swin-Unet [17-18] combine CNN and Transformer. "
            "Yet, existing methods struggle with small targets, dense instances, blurred boundaries, and lack quantitative readout."
        ),
        "proposed_solution": (
            "MorphoMask proposes WT-DPE (weak-boundary dual-path enhancement module) for detail enhancement and cross-path fusion, "
            "and SLAC (spatial location alignment calibration module) for spatial orientation modeling. "
            "It outputs both segmentation masks and morphological parameters (number, area, perimeter, minor axis length, aspect ratio)."
        )
    },
    "methods": {
        "wt_dpe": (
            "Weak-boundary dual-path enhancement module (WT-DPE): embedded in high-resolution feature layer. "
            "Detail enhancement path and cross-path fusion strengthen representation of local textures, subtle boundaries, and small targets."
        ),
        "slac": (
            "Spatial location alignment calibration module (SLAC): introduced into fused key features. "
            "Improves modeling accuracy of orientation-related spatial information and enhances separation of adjacent instances."
        ),
        "morphological_quantification": (
            "Instance-level and image-level parameters extracted: number, area, perimeter, minor axis length, aspect ratio. "
            "Forms an integrated automated analysis workflow."
        )
    },
    "contributions": [
        "Proposed WT-DPE: detail enhancement and cross-path fusion for small targets, subtle boundaries, and adherent regions.",
        "Proposed SLAC: spatial orientation modeling for dense instance separation.",
        "Integrated workflow: segmentation masks -> morphological indicators for organoid culture monitoring and automated phenotypic analysis."
    ],
    "conclusion": (
        "MorphoMask provides accurate, stable, and quantifiable bright-field organoid image analysis. "
        "It addresses small-object representation, dense instance separation, and quantitative analysis. "
        "The method has practical value for organoid culture monitoring and automated phenotypic analysis."
    )
}

# ========= Generate markdown file =========
contributions_str = "".join(["- " + c + "\n" for c in paper_summary['contributions']])

markdown_content = f"""# Paper Summary: MorphoMask

## Title
{paper_summary['title']}

## Abstract
{paper_summary['abstract']}

## Introduction
### Background
{paper_summary['introduction']['background']}

### Problem Statement
{paper_summary['introduction']['problem']}

### Existing Methods
{paper_summary['introduction']['methods_overview']}

### Proposed Solution
{paper_summary['introduction']['proposed_solution']}

## Methods
### WT-DPE (Weak-boundary Dual-path Enhancement Module)
{paper_summary['methods']['wt_dpe']}

### SLAC (Spatial Location Alignment Calibration Module)
{paper_summary['methods']['slac']}

### Morphological Quantification
{paper_summary['methods']['morphological_quantification']}

## Contributions
{contributions_str}
## Conclusion
{paper_summary['conclusion']}

## References (from prompt)
[1] Sato et al. (intestinal organoids)  
[2] Lancaster and Knoblich (organoid potential)  
[3] Clevers (disease modeling, regenerative medicine)  
[4-9] OrganoSeg, OrganoID, OrganelX, OrgaSegment, D-CryptO, POST  
[10-16] U-Net, Mask R-CNN, Transformer, MaskFormer, Mask2Former  
[17-18] TransUNet, Swin-Unet  
[23] Unified modeling for small-object representation, dense separation, quantitative analysis
"""

output_file = OUTPUT_DIR / "paper_summary.md"
output_file.write_text(markdown_content, encoding="utf-8")

# Also write to references for documentation
ref_file = REFERENCES_DIR / "paper_summary.md"
ref_file.write_text(markdown_content, encoding="utf-8")

# ========= Generate JSON with metadata (optional) =========
metadata = {
    "run_id": RUN_ID,
    "skill": "nature-citation",
    "paper_title": paper_summary["title"],
    "output_files": [str(output_file), str(ref_file)],
    "key_contributions": paper_summary["contributions"]
}

metadata_file = OUTPUT_DIR / "metadata.json"
metadata_file.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

# ========= Confirm completion =========
print(f"Generated paper summary and metadata in {OUTPUT_DIR}")
