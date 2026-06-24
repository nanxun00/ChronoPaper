#!/usr/bin/env python3
import re
import sys
import os
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("Error: PyMuPDF (fitz) is required. Install with: pip install PyMuPDF")
    sys.exit(1)

# --- 配置常量 ---
RUN_ID = "BXjERfBIeFhuiFxd"
PDF_PATH = Path("input/papers/doi_10.1016_j.neucom.2023.126295/paper.pdf")
FIGURES_DIR = Path("output/assets/figures")
OUTPUT_DIR = Path(f"output/runs/{RUN_ID}")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_MD = OUTPUT_DIR / "TISS_net_bilingual.md"

# 使用列出的论文配图文件名（顺序用于映射图表引用）
FIGURE_FILES = [
    "doi_10.1016_j.neucom.2023.126295_mineru_0472a3fd900ad606d4d4dff7cecf6430ad588700bd84ad8dc3e8d6aa0b3dd2f4.jpg",
    "doi_10.1016_j.neucom.2023.126295_mineru_0ff6e8b69ec28bbf0c9c05e5588a71682d9c60474a9171561b61702c93692fc2.jpg",
    "doi_10.1016_j.neucom.2023.126295_mineru_3b67bc3e898c27df116211582c813e6ecf7d4a9e9ccb265e93076a43c86fcbe9.jpg",
    "doi_10.1016_j.neucom.2023.126295_mineru_3c4cf201f0d1f318cb49b829b7fd547aed8a71696413fe6b5ed6eb537b605004.jpg",
    "doi_10.1016_j.neucom.2023.126295_mineru_3ceb43e950c1950491d9a3571202ef496b748c0b82c371b29e222942743214ec.jpg",
    "doi_10.1016_j.neucom.2023.126295_mineru_420a8638206555cc3146017bf2c5be6381a379a30199db9e9de60d8dce14ec15.jpg",
    "doi_10.1016_j.neucom.2023.126295_mineru_619b2d3b01d4932b7fc72b01b4d30682f284867fa7f44b8620ce8b79e21370bc.jpg",
    "doi_10.1016_j.neucom.2023.126295_mineru_6c885d1c0b00af837aa131e425e76b35046a3846d660a55ce069f9072bbf425d.jpg",
    "doi_10.1016_j.neucom.2023.126295_mineru_72bb6f6e69542888b6b98f6d4fe714c82427261e0bcea392e07fd74b1d3a2ea8.jpg",
    "doi_10.1016_j.neucom.2023.126295_mineru_756d738f3023c2eb61c7cf89e1ca80b6a0cabc727d2c8d7d98af6bd34582ca05.jpg",
    "doi_10.1016_j.neucom.2023.126295_mineru_77dc723697dcf9bfd2ef8340c1468121fc7d0ac444abfa9e7030326baef40eb7.jpg",
    "doi_10.1016_j.neucom.2023.126295_mineru_80d162fafe7766ffd16931e78a3730a7793de32deff215202732948f65163b47.jpg",
    "doi_10.1016_j.neucom.2023.126295_mineru_85c3f9ff0a7aabe76954796e9d29c3be56dd4896c8a41b28800a528d80eb2240.jpg",
    "doi_10.1016_j.neucom.2023.126295_mineru_8e6ed6d18b09f3573cb4e827c64be830c77dae5d86536e245fa1d4645a43228a.jpg",
    "doi_10.1016_j.neucom.2023.126295_mineru_a0a3beba44d28d17f16690c94fbb272f937a8f96f15c378731d31d23e9b3b116.jpg",
    "doi_10.1016_j.neucom.2023.126295_mineru_ad32e7df5054a06f933877c78fd5a01b920d14a280d258d2cac3ace16a3663c1.jpg",
    "doi_10.1016_j.neucom.2023.126295_mineru_b90d637f95a9ae83e15f18924bb30115a1617bbd4482e879832e26f609598a4c.jpg",
    "doi_10.1016_j.neucom.2023.126295_mineru_b9b1eb34cbe3fb3901a653f36e6937a1e40f068993570ebc17de1abba7db9d7b.jpg",
    "doi_10.1016_j.neucom.2023.126295_mineru_bde078d069c1600358d9dc57b36c792f8c2804352f896d76bfcc8fa52b665068.jpg",
    "doi_10.1016_j.neucom.2023.126295_mineru_c180dcd4923d03e568e4b1fd9b1888668e3fcc53ed2ce20647e325cfc0dff25a.jpg",
    "doi_10.1016_j.neucom.2023.126295_mineru_ca582d1e65dbdb37ce39cd0193a9e90f0f3461d3ba76b82d3e12384cc88b8f9c.jpg",
    "doi_10.1016_j.neucom.2023.126295_mineru_cc5894304a9bf29f9955b46b81ac6d33461a41f22c0cdc485a633929ccea727c.jpg",
    "doi_10.1016_j.neucom.2023.126295_mineru_cec9b730b240eef2e017a9bdaf33882f19d3648e1fba4629bc70ecdd44768a81.jpg",
    "doi_10.1016_j.neucom.2023.126295_mineru_d06b1f106d0b4ce754999a27a77c18fe494a86f2deb973708786e1f985af99f4.jpg",
    "doi_10.1016_j.neucom.2023.126295_mineru_d327b82907e6cf597756a1b989673033533dbddb7334e5a9069347da70dbf298.jpg",
    "doi_10.1016_j.neucom.2023.126295_mineru_de2beea4c7433de7a02bbdd65d22289f889aa00da4f6ee0ecf72f907712d06b7.jpg",
    "doi_10.1016_j.neucom.2023.126295_mineru_e60adf9533ef8d41b47559749b0f175e2c0aedf2bb0c887e148f5cb15ac4ab11.jpg",
    "doi_10.1016_j.neucom.2023.126295_mineru_eb021f5c3a0ccade553e03d7cbcb3f57983dd7d71145e456926ee5f161386f93.jpg",
    "doi_10.1016_j.neucom.2023.126295_mineru_f267924522a4568f5f9875a63c3490c81c30362a865a7c6823fccdd62ed02dc7.jpg",
    "doi_10.1016_j.neucom.2023.126295_mineru_f3640964401a15007b29304c5017a3674a156d023bf70c634f1e53ee7bce52f1.jpg",
]

# 评测指标保留英文
METRICS_KEEP_ENGLISH = ["Dice", "ASSD", "SSIM"]

def extract_text_from_pdf(pdf_path):
    """提取PDF的全部文本，保留基本结构。"""
    try:
        doc = fitz.open(pdf_path)
        full_text = ""
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            blocks = page.get_text("blocks")
            for block in blocks:
                if block[6] == 0:  # 文本块
                    text = block[4].strip()
                    if text:
                        full_text += text + "\n\n"
        doc.close()
        return full_text
    except Exception as e:
        print(f"Error reading PDF {pdf_path}: {e}")
        return None

def simple_translate_paragraph(eng_para):
    """提供占位翻译，保留专业术语。"""
    if not eng_para.strip():
        return ""
    # 保留评测指标
    zh_para = eng_para
    # 简单替换常见术语（示意）
    term_map = {
        "TISS-net": "TISS-net",
        "segmentation": "分割",
        "medical image": "医学图像",
        "method": "方法",
        "experiment": "实验",
        "result": "结果",
        "Table": "表",
        "Fig.": "图",
        "Figure": "图",
        "ablation": "消融",
        "network": "网络",
        "training": "训练",
        "inference": "推理",
        "loss": "损失函数",
        "dataset": "数据集",
        "architecture": "架构",
        "module": "模块",
        "attention": "注意力",
        "feature": "特征",
    }
    for eng_term, zh_term in term_map.items():
        zh_para = zh_para.replace(eng_term, zh_term)
    # 标记翻译占位
    return f"[中文翻译待定] {zh_para}"

def parse_paper_structure(text):
    """尝试将文本分割为章节、段落，并识别图表锚点。"""
    sections = []
    current_section = {"title": "Introduction", "paragraphs": []}
    
    section_pattern = re.compile(
        r"^(?P<header>(?:Abstract|Introduction|Related Work|Method(?:ology)?|"
        r"Experiment(?:s|al Results)?|Discussion|Conclusion|Acknowledg(?:e)?ment|"
        r"Reference(?:s)?|Appendix).*)",
        re.MULTILINE | re.IGNORECASE
    )
    figure_pattern = re.compile(r"(?:Fig(?:ure|\.)\s*\d+|Table\s*\d+)", re.IGNORECASE)
    
    lines = text.split('\n')
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue
        
        match = section_pattern.match(line_stripped)
        if match:
            if current_section["paragraphs"]:
                sections.append(current_section)
            current_section = {
                "title": match.group("header").strip(),
                "paragraphs": []
            }
        else:
            if current_section["paragraphs"]:
                current_section["paragraphs"][-1]["text_en"] += " " + line_stripped
            else:
                current_section["paragraphs"].append({
                    "text_en": line_stripped,
                    "figure_refs": []
                })
            figure_matches = figure_pattern.findall(line_stripped)
            if figure_matches and current_section["paragraphs"]:
                current_section["paragraphs"][-1]["figure_refs"].extend(figure_matches)
    
    if current_section["paragraphs"]:
        sections.append(current_section)
    return sections

def generate_markdown(sections):
    """生成中英文对照Markdown内容。"""
    md_lines = []
    md_lines.append("# TISS-net 论文全文中英文对照阅读文档")
    md_lines.append(f"**运行ID:** `{RUN_ID}`")
    md_lines.append(f"**源PDF:** `{PDF_PATH}`")
    md_lines.append(f"**图表目录:** `{FIGURES_DIR}`")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")
    
    # 按主要章节分组
    method_sections = []
    experiment_sections = []
    discussion_sections = []
    other_sections = []
    
    for section in sections:
        title = section["title"].lower()
        if any(kw in title for kw in ["method", "approach", "proposed", "architecture", "network"]):
            method_sections.append(section)
        elif any(kw in title for kw in ["experiment", "result", "evaluation", "ablation", "comparison"]):
            experiment_sections.append(section)
        elif any(kw in title for kw in ["discussion", "conclusion", "analysis"]):
            discussion_sections.append(section)
        else:
            other_sections.append(section)
    
    def write_section_group(group_title, group_sections):
        if not group_sections:
            return
        md_lines.append(f"## {group_title}")
        md_lines.append("")
        for section in group_sections:
            md_lines.append(f"### {section['title']}")
            md_lines.append("")
            for para in section["paragraphs"]:
                md_lines.append("**英文原文:**")
                md_lines.append(f"> {para['text_en']}")
                md_lines.append("")
                zh_text = simple_translate_paragraph(para["text_en"])
                md_lines.append("**中文翻译:**")
                md_lines.append(f"> {zh_text}")
                md_lines.append("")
                if para["figure_refs"]:
                    unique_refs = list(dict.fromkeys(para["figure_refs"]))  # 去重保序
                    md_lines.append("**关联图表:**")
                    for ref in unique_refs:
                        ref_clean = ref.strip().lower().replace(".", "")
                        # 尝试提取数字并映射到提供的图片文件
                        num_match = re.search(r'\d+', ref_clean)
                        if num_match:
                            num_str = num_match.group()
                            fig_idx = int(num_str) - 1
                            if 0 <= fig_idx < len(FIGURE_FILES):
                                fig_filename = FIGURE_FILES[fig_idx]
                                fig_path = FIGURES_DIR / fig_filename
                                if fig_path.exists():
                                    # 计算相对于 OUTPUT_DIR 的路径
                                    try:
                                        rel_path = os.path.relpath(fig_path, OUTPUT_DIR)
                                    except ValueError:
                                        rel_path = fig_path
                                    md_lines.append(f"![{ref}]({rel_path})")
                                else:
                                    md_lines.append(f"- {ref} (配图文件未找到)")
                            else:
                                md_lines.append(f"- {ref} (超出提供图片范围)")
                        else:
                            md_lines.append(f"- {ref}")
                    md_lines.append("")
        md_lines.append("---")
        md_lines.append("")
    
    # 按顺序写入
    if other_sections:
        write_section_group("其他章节 (Other Sections)", other_sections)
    if method_sections:
        write_section_group("方法章节 (Method Sections)", method_sections)
    if experiment_sections:
        write_section_group("实验章节 (Experiment Sections)", experiment_sections)
    if discussion_sections:
        write_section_group("讨论章节 (Discussion Sections)", discussion_sections)
    
    return "\n".join(md_lines)

def main():
    if not PDF_PATH.exists():
        print(f"Error: PDF file not found: {PDF_PATH}")
        sys.exit(1)
    
    text = extract_text_from_pdf(PDF_PATH)
    if not text:
        print("Failed to extract text from PDF.")
        sys.exit(1)
    
    sections = parse_paper_structure(text)
    md_content = generate_markdown(sections)
    
    try:
        with open(OUTPUT_MD, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"Bilingual Markdown saved to: {OUTPUT_MD}")
    except Exception as e:
        print(f"Error writing Markdown file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
