from src.services.graph.graph_query_router import (
    ENTITY_SIM_THRESHOLD,
    classify_intent_by_keywords,
    entity_match_score,
    parse_typed_entities_raw,
    sanitize_entity_raw,
    _filter_chunks_by_section,
)
from src.services.rag.retrieval_fusion import (
    build_fused_external,
    dedup_graph_chunks,
    should_use_graph,
    simhash_similarity,
)


def test_parse_typed_entities_json():
    raw = '{"entities": [{"raw_name": "TISS-Net", "entity_type": "Model"}, {"raw_name": "Dice", "entity_type": "Metric"}]}'
    items = parse_typed_entities_raw(raw)
    assert len(items) == 2
    assert items[0]["entity_type"] == "Model"
    assert items[1]["raw_name"] == "Dice"


def test_sanitize_entity_rejects_garbage():
    assert sanitize_entity_raw("TISS-Net") == "TISS-Net"
    assert sanitize_entity_raw("sota\uFFFD\uFFFD") == ""
    assert sanitize_entity_raw("a") == ""


def test_entity_match_score_exact_and_substring():
    assert entity_match_score("TISS-Net", "TISS-Net") == 1.0
    assert entity_match_score("tiss", "TISS-Net") == 1.0
    assert entity_match_score("xyz", "abc") < ENTITY_SIM_THRESHOLD


def test_classify_intent_by_keywords():
    assert classify_intent_by_keywords("这篇论文引用了哪些工作") == "Citation_Relate"
    assert classify_intent_by_keywords("Dice 指标是多少") == "Metric_Eval"
    assert classify_intent_by_keywords("用了什么 BraTS 数据集") == "Dataset_Use"
    assert classify_intent_by_keywords("和 SOTA 方法对比") == "Compare_SOTA"
    assert classify_intent_by_keywords("TISS-Net 基于什么改进") == "Model_Improve"
    assert classify_intent_by_keywords("整体创新点是什么") == "General_Summary"


def test_should_use_graph_general_summary_off():
    assert should_use_graph("General_Summary", True) is False
    assert should_use_graph("Metric_Eval", True) is True


def test_dedup_graph_chunks_against_vector():
    kb = [{"entity": {"text": "BraTS 2020 dataset with T1 T2 FLAIR modalities for segmentation"}}]
    graph = [{"chunk_id": "g1", "chunk_text": "BraTS 2020 dataset with T1 T2 FLAIR modalities"}]
    kept = dedup_graph_chunks(graph, kb, threshold=0.8)
    assert kept == []


def test_build_fused_external_vector_first():
    kb = [{"id": "1", "entity": {"text": "vector evidence"}}]
    graph = {
        "intent": "Metric_Eval",
        "chunks": [],
        "edges": [{"source_name": "A", "target_name": "B", "type": "评测指标", "rel_type": "EVALUATE_BY"}],
        "chain_summary": "",
        "sota_summary": "",
        "cite_summary": "",
    }
    text = build_fused_external(kb, graph, intent="Metric_Eval", use_graph=True)
    assert "【主证据 · 知识库原文】" in text
    assert text.index("主证据") < text.index("图谱补充")


def test_simhash_similarity_identical():
    assert simhash_similarity("hello world test", "hello world test") == 1.0
