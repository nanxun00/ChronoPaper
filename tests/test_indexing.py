"""MinerU 论文分块规则测试。"""
from __future__ import annotations

from src.services.rag.indexing import (
    _should_drop_block,
    chunk_paper_content_list,
)


def _sample_tissnet_blocks() -> list[dict]:
    return [
        {"type": "text", "text": "13", "page_idx": 0},
        {"type": "text", "text": "Neurocomputing 544 (2023) 126295", "page_idx": 0},
        {"type": "text", "text": "© 2023 Elsevier B.V. All rights reserved.", "page_idx": 0},
        {"type": "text", "text": "https://doi.org/10.1016/j.neucom.2023.126295", "page_idx": 0},
        {
            "type": "text",
            "text": "TISS-net: Brain tumor image synthesis and segmentation using cascaded dual-task networks",
            "text_level": 1,
            "page_idx": 0,
        },
        {
            "type": "text",
            "text": "Jian Wang¹, Li Zhang², Ming Zhao¹,*",
            "page_idx": 0,
        },
        {
            "type": "text",
            "text": "School of Mechanical and Electrical Engineering, UESTC, Chengdu, China",
            "page_idx": 0,
        },
        {
            "type": "text",
            "text": "Department of Radiology, West China Hospital, Sichuan University, Chengdu, China",
            "page_idx": 0,
        },
        {
            "type": "text",
            "text": "Abstract",
            "text_level": 1,
            "page_idx": 0,
        },
        {
            "type": "text",
            "text": (
                "Brain tumor segmentation is a critical task in medical image analysis. "
                "We propose TISS-net, a cascaded dual-task network for synthesis and segmentation."
            ),
            "page_idx": 0,
        },
        {
            "type": "text",
            "text": "CRediT authorship contribution statement: J.W. conceptualization; L.Z. methodology.",
            "page_idx": 5,
        },
        {
            "type": "text",
            "text": "Jian Wang received his Ph.D. from UESTC and is currently a professor at the same school.",
            "page_idx": 6,
        },
    ]


def test_drop_noise_blocks():
    assert _should_drop_block("13", "text", "text")
    assert _should_drop_block("© 2023 Elsevier B.V. All rights reserved.", "text", "text")
    assert _should_drop_block("https://doi.org/10.1016/j.neucom.2023.126295", "text", "text")
    assert _should_drop_block(
        "CRediT authorship contribution statement: J.W. conceptualization.",
        "text",
        "text",
    )
    assert _should_drop_block(
        "Jian Wang received his Ph.D. from UESTC and is currently a professor at the same school.",
        "text",
        "reference",
    )


def test_merge_title_authors_affiliations():
    rows = chunk_paper_content_list(
        _sample_tissnet_blocks(),
        kb_id="test_kb",
        paper_id="doi:test",
    )
    title_chunks = [r for r in rows if r["block_type"] == "title"]
    assert len(title_chunks) == 1
    merged = title_chunks[0]["chunk_text"]
    assert "TISS-net" in merged
    assert "Jian Wang" in merged
    assert "UESTC" in merged
    assert "West China Hospital" in merged
    assert all(r["chunk_text"].strip() != "13" for r in rows)


def test_keep_abstract_intact():
    rows = chunk_paper_content_list(
        _sample_tissnet_blocks(),
        kb_id="test_kb",
        paper_id="doi:test",
    )
    abstract_chunks = [r for r in rows if r["section_type"] == "abstract"]
    assert len(abstract_chunks) == 1
    assert "Brain tumor segmentation" in abstract_chunks[0]["chunk_text"]
