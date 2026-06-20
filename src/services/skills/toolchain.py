"""Nature 技能 Python 工具链：依赖清单与可用性检查。"""
from __future__ import annotations

from dataclasses import dataclass

# 按技能/场景分组的 import 探测（模块名 → pip 包名）
_SKILL_IMPORT_CHECKS: list[tuple[str, str, str]] = [
    ("fitz", "pymupdf", "paper2ppt, reader, input_sync"),
    ("pptx", "python-pptx", "paper2ppt"),
    ("PIL", "pillow", "paper2ppt, figure, patent"),
    ("docx", "python-docx", "paper-to-patent"),
    ("pypdf", "pypdf", "paper-to-patent"),
    ("lxml", "lxml", "citation, academic-search MCP"),
    ("yaml", "pyyaml", "技能 manifest"),
    ("matplotlib", "matplotlib", "nature-figure"),
    ("seaborn", "seaborn", "nature-figure"),
    ("scipy", "scipy", "nature-figure"),
    ("statsmodels", "statsmodels", "nature-figure"),
    ("tifffile", "tifffile", "nature-figure TIFF 导出"),
    ("skimage", "scikit-image", "nature-figure 图像处理"),
    ("latex2mathml", "latex2mathml", "paper-to-patent 公式"),
]

CODEGEN_ALLOWED_PACKAGES_TEXT = """\
- 标准库：pathlib、json、re、csv、zipfile、xml、tempfile、io 等（优先写到 output/runs/{run_id}/，少用系统临时目录）
- 文档：pptx (python-pptx)、PIL/Pillow、fitz (PyMuPDF)、docx (python-docx)、pypdf
- 绘图：matplotlib、seaborn、scipy、statsmodels、tifffile、skimage (scikit-image)
- 专利公式：latex2mathml
- 输出目录：output/、references/；配图目录：output/assets/figures/
- 清理：用 mkdir(exist_ok=True) 覆盖写入；勿 rmtree 删除 references/figures/SKILL.md"""


@dataclass
class ToolchainReport:
    missing: list[str]
    present: list[str]

    @property
    def ok(self) -> bool:
        return not self.missing


def check_skill_toolchain() -> ToolchainReport:
    """探测技能脚本/codegen 常用包是否可 import。"""
    missing: list[str] = []
    present: list[str] = []
    for mod, pip_name, _ in _SKILL_IMPORT_CHECKS:
        try:
            __import__(mod)
            present.append(f"{mod} ({pip_name})")
        except ImportError:
            missing.append(f"{mod} ← pip install {pip_name}")
    return ToolchainReport(missing=missing, present=present)
