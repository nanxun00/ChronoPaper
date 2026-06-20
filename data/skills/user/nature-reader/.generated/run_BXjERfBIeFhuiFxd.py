#!/usr/bin/env python3
import re
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("Error: PyMuPDF (fitz) is required. Install with: pip install PyMuPDF")
    sys.exit(1)

try:
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
except ImportError:
    print("Error: python-docx is required. Install with: pip install python-docx")
    sys.exit(1)

# --- 配置常量 ---
RUN_ID = "BXjERfBIeFhuiFxd"
# 使用明确列出的路径
PDF_PATH = Path("input/papers/doi_10.1016_j.neucom.2023.126295/paper.pdf")
FIGURES_DIR = Path("output/assets/figures")
# 使用列出的论文配图文件名
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

OUTPUT_DIR = Path(f"output/runs/{RUN_ID}")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# --- 1. 提取PDF全文文本 ---
def extract_text_from_pdf(pdf_path):
    """提取PDF的全部文本。"""
    try:
        doc = fitz.open(pdf_path)
        full_text = ""
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            # 提取文本块，保留基本段落结构
            blocks = page.get_text("blocks")
            for block in blocks:
                # 块格式: (x0, y0, x1, y1, "text", block_no, block_type)
                # 只处理文本块 (block_type == 0)
                if block[6] == 0:
                    text = block[4].strip()
                    if text:
                        # 添加换行以分隔不同块
                        full_text += text + "\n\n"
        doc.close()
        return full_text
    except Exception as e:
        print(f"Error reading PDF {pdf_path}: {e}")
        return None

# --- 2. 简单英文段落到中文的翻译占位符 ---
# 注意：真实场景需要集成翻译API。这里使用基于上下文的占位翻译。
def simple_translate_paragraph(eng_para):
    """提供一个基于关键词的简单翻译示例。实际应用需替换为真实翻译。"""
    # 这是一个极简的、基于模式的翻译示例，用于演示结构。
    # 真实实现应该使用翻译模型或API。
    if not eng_para.strip():
        return ""
    
    # 为常见术语创建映射（仅作为示例）
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
        "Dice": "Dice",
        "ASSD": "ASSD",
        "SSIM": "SSIM",
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
    
    # 简单的替换演示（不完整，仅示意）
    zh_para = eng_para
    for eng_term, zh_term in term_map.items():
        zh_para = zh_para.replace(eng_term, zh_term)
    
    # 在真实翻译中，这里应该调用翻译服务。
    # 由于无法访问网络，这里我们标记为“翻译待定”。
    # 我们将保留英文原文并添加一个标记，表明这是需要翻译的部分。
    return f"[中文翻译待定] {zh_para}"

# --- 3. 解析论文结构并生成Markdown ---
def parse_paper_structure(text):
    """尝试将文本分割为章节、段落，并识别图表锚点。"""
    sections = []
    current_section = {"title": "Introduction", "paragraphs": []}
    
    # 简单的章节标题识别（基于常见模式）
    section_pattern = re.compile(
        r"^(?P<header>(?:Abstract|Introduction|Related Work|Method(?:ology)?|"
        r"Experiment(?:s|al Results)?|Discussion|Conclusion|Acknowledg(?:e)?ment|"
        r"Reference(?:s)?|Appendix).*)",
        re.MULTILINE | re.IGNORECASE
    )
    
    # 图表引用模式
    figure_pattern = re.compile(r"(?:Fig(?:ure|\.)\s*\d+|Table\s*\d+)", re.IGNORECASE)
    
    # 按行分割文本
    lines = text.split('\n')
    last_pos = 0
    
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue
        
        # 检查是否是章节标题
        match = section_pattern.match(line_stripped)
        if match:
            # 保存当前段落（如果有）
            if current_section["paragraphs"]:
                sections.append(current_section)
            # 开始新章节
            current_section = {
                "title": match.group("header").strip(),
                "paragraphs": []
            }
        else:
            # 将行作为段落的一部分添加
            if current_section["paragraphs"]:
                current_section["paragraphs"][-1]["text_en"] += " " + line_stripped
            else:
                # 新段落
                current_section["paragraphs"].append({
                    "text_en": line_stripped,
                    "figure_refs": []
                })
            
            # 检查本行是否有图表引用
            figure_matches = figure_pattern.findall(line_stripped)
            if figure_matches and current_section["paragraphs"]:
                current_section["paragraphs"][-1]["figure_refs"].extend(figure_matches)
    
    # 添加最后一个章节
    if current_section["paragraphs"]:
        sections.append(current_section)
    
    return sections

def generate_markdown_with_figures(sections):
    """生成带有图表引用和中英文对照的Markdown。"""
    md_lines = []
    md_lines.append(f"# TISS-net 论文全文中英文对照阅读文档")
    md_lines.append(f"**运行ID:** `{RUN_ID}`")
    md_lines.append(f"**源PDF:** `{PDF_PATH}`")
    md_lines.append(f"**图表目录:** `{FIGURES_DIR}`")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")
    
    # 按主要章节分组（方法、实验、讨论）
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
    
    def write_section_group(group_title, group_sections, md_lines):
        if not group_sections:
            return
        md_lines.append(f"## {group_title}")
        md_lines.append("")
        
        for section in group_sections:
            # 章节标题
            md_lines.append(f"### {section['title']}")
            md_lines.append("")
            
            # 段落
            for para in section["paragraphs"]:
                # 英文原文
                md_lines.append(f"**英文原文:**")
                md_lines.append(f"> {para['text_en']}")
                md_lines.append("")
                
                # 中文翻译（占位符）
                zh_text = simple_translate_paragraph(para["text_en"])
                md_lines.append(f"**中文翻译:**")
                md_lines.append(f"> {zh_text}")
                md_lines.append("")
                
                # 图表引用与绑定
                if para["figure_refs"]:
                    unique_refs = list(dict.fromkeys(para["figure_refs"]))  # 去重并保序
                    md_lines.append(f"**关联图表:**")
                    for ref in unique_refs:
                        # 尝试查找对应的论文配图文件（这里使用文件列表索引作为示例）
                        # 真实场景需要建立图表编号到文件名的映射
                        ref_clean = ref.strip().lower().replace(".", "")
                        # 简单的索引映射（演示用）
                        try:
                            if "fig" in ref_clean or "figure" in ref_clean:
                                # 提取数字，用作索引（减1因为Python索引从0开始）
                                num_str = re.search(r'\d+', ref_clean).group()
                                fig_idx = int(num_str) - 1
                                if 0 <= fig_idx < len(FIGURE_FILES):
                                    fig_filename = FIGURE_FILES[fig_idx]
                                    fig_path = FIGURES_DIR / fig_filename
                                    if fig_path.exists():
                                        md_lines.append(f"![{ref}]({fig_path})")
                                        md_lines.append("")
                                    else:
                                        md_lines.append(f"- {ref} (配图文件未找到: {fig_path})")
                                else:
                                    md_lines.append(f"- {ref} (无法映射到提供的配图文件)")
                            else:
                                md_lines.append(f"- {ref}")
                        except:
                            md_lines.append(f"- {ref}")
        
        md_lines.append("---")
        md_lines.append("")
    
    # 按顺序写入各部分
    if other_sections:
        # 其他部分（摘要、引言、相关工作等）
        write_section_group("其他章节 (Other Sections)", other_sections, md_lines)
    if method_sections:
        write_section_group("方法章节 (Method Sections)", method_sections, md_lines)
    if experiment_sections:
        write_section_group("实验章节 (Experiment Sections)", experiment_sections, md_lines)
    if discussion_sections:
        write_section_group("讨论章节 (Discussion Sections)", discussion_sections, md_lines)
    
    # 附录：提供的配图文件列表
    md_lines.append("## 附录：可用论文配图文件列表")
    md_lines.append("")
    md_lines.append(f"以下文件位于 `{FIGURES_DIR}` 目录，可供插入幻灯片或文档：")
    md_lines.append("")
    for i, fig_file in enumerate(FIGURE_FILES):
        full_path = FIGURES_DIR / fig_file
        exists = full_path.exists()
        status = "✓" if exists else "✗"
        md_lines.append(f"{i+1}. `{fig_file}` - {status}")
    md_lines.append("")
    
    return "\n".join(md_lines)

# --- 主流程 ---
def main():
    print(f"开始处理论文: {PDF_PATH}")
    
    # 检查文件是否存在
    if not PDF_PATH.exists():
        print(f"错误: PDF文件不存在于 {PDF_PATH.resolve()}")
        print("请确保将论文放置在正确的路径下。")
        return
    
    # 1. 提取文本
    print("正在提取PDF文本...")
    full_text = extract_text_from_pdf(PDF_PATH)
    if not full_text:
        print("错误: 无法从PDF中提取文本。")
        return
    print(f"成功提取文本，长度: {len(full_text)} 字符")
    
    # 2. 解析结构
    print("正在解析论文结构...")
    sections = parse_paper_structure(full_text)
    print(f"识别出 {len(sections)} 个章节/部分")
    
    # 3. 生成Markdown
    print("正在生成中英文对照Markdown文档...")
    markdown_content = generate_markdown_with_figures(sections)
    
    # 4. 保存文件
    output_file = OUTPUT_DIR / "TISS_net_Bilingual_Readme.md"
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        print(f"文档已成功生成并保存至: {output_file.resolve()}")
    except Exception as e:
        print(f"错误: 无法写入文件 {output_file}: {e}")
        return
    
    print(f"\n完成！主交付文件: {output_file.resolve()}")
    print("注意：中文翻译部分为占位符，实际内容需使用翻译服务完善。")
    print("图表绑定基于简单索引映射，实际使用中可能需要调整映射逻辑。")

if __name__ == "__main__":
    main()
