# Nature 技能工具链对照表

ChronoPaper 主环境依赖见项目根目录 `requirements.txt` 第 18 节。  
MCP 子服务（可选）见 `requirements-skills-mcp.txt`。

## 按技能汇总

| 技能 | 主要产出 | Python 包（已纳入 requirements） | 脚本 | 备注 |
|------|----------|-------------------------------|------|------|
| nature-academic-search | 检索 JSON、.bib/.ris | stdlib + urllib | `academic_search.py`, `format-converter.py` | MCP 需另装 |
| nature-citation | .enw/.ris 引文 | stdlib + urllib | `nature_citation.py` | |
| nature-paper2ppt | .pptx | pymupdf, pillow, python-pptx | codegen + `build_pptx.py` | 需引用文献 PDF |
| nature-figure | .svg/.pdf/.png/.tiff | matplotlib, seaborn, scipy, statsmodels, tifffile, scikit-image | codegen | R 后端需本机 R |
| nature-paper-to-patent | .docx 专利包 | python-docx, pypdf, pillow, **latex2mathml** | 8 个 scripts | |
| nature-reader | Markdown 阅读稿 | pymupdf（codegen） | 无内置脚本 | 文本型为主 |
| nature-writing | 文稿 | 无 | 无 | 纯 LLM |
| nature-polishing | 润色文稿 | pymupdf（LaTeX 排版诊断） | 无 | |
| nature-reviewer | 审稿意见 | 无 | 无 | 纯 LLM |
| nature-response | 回复信 | 无 | 无 | 纯 LLM |
| nature-data | 数据声明 | 无 | 无 | 纯 LLM |

## 项目已具备（requirements 原有）

- pymupdf, python-pptx, pillow, python-docx, pypdf, lxml, openpyxl, pyyaml, numpy, pandas, requests

## 本次补充（requirements §18）

- `latex2mathml` — patent 公式 → Office Math
- `matplotlib`, `seaborn`, `scipy`, `statsmodels` — figure 科研绘图
- `tifffile`, `scikit-image` — figure TIFF / 图像处理

## 未接入主流程（需单独处理）

| 组件 | 说明 |
|------|------|
| **R 运行时** | nature-figure R 后端；`Rscript` + ggplot2 等需用户本机安装 |
| **LibreOffice** | paper2ppt 可选 PPT 预览；未集成 |
| **MCP 服务** | `nature-academic-search/mcp-server/`；`pip install -r requirements-skills-mcp.txt` |
| **pybiliometrics** | Scopus API；需 API Key，仅 MCP 使用 |

## 检查命令

```powershell
$env:PYTHONPATH="."
E:\conda_config\envs\chronopaper\python.exe tests\test_skill_toolchain.py
```

安装缺失包：

```powershell
pip install -r requirements.txt
```
