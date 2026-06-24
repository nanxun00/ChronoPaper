from src.services.graph.extraction import (
    collect_entities_for_upsert,
    merge_extraction_batches,
    resolve_task_domain,
)


def test_merge_extraction_batches_keeps_longer_description():
    merged = merge_extraction_batches([
        {
            "task_domain": "图像分割",
            "raw_entities": [
                {
                    "raw_name": "Dice",
                    "std_name": "dice",
                    "entity_type": "Metric",
                    "chunk_id": "c1",
                    "description": "Dice 系数。",
                }
            ],
            "relations_raw": [],
        },
        {
            "task_domain": None,
            "raw_entities": [
                {
                    "raw_name": "Dice",
                    "std_name": "dice",
                    "entity_type": "Metric",
                    "chunk_id": "c2",
                    "description": "Dice 系数是分割评价指标，公式为 2|A∩B|/(|A|+|B|)。",
                }
            ],
            "relations_raw": [],
        },
    ])

    assert merged["task_domain"] == "图像分割"
    entities = merged["raw_entities"]
    assert len(entities) == 1
    assert "公式" in entities[0]["description"]


def test_collect_entities_for_upsert_includes_relation_endpoints():
    merged = {
        "raw_entities": [
            {
                "raw_name": "TISS-Net",
                "std_name": "tissnet",
                "entity_type": "Model",
                "chunk_id": "c1",
                "description": "级联网络",
            }
        ],
    }
    relations_std = [
        {
            "source_std": "paper:1",
            "target_std": "t1",
            "source_type": "Paper",
            "target_type": "Dataset",
            "rel_type": "USE_DATASET",
        },
        {
            "source_std": "paper:1",
            "target_std": "dice",
            "source_type": "Paper",
            "target_type": "Metric",
            "rel_type": "EVALUATE_BY",
        },
    ]
    items = collect_entities_for_upsert("paper:1", merged, relations_std)
    names = {i["std_name"] for i in items}
    assert names == {"tissnet", "t1", "dice"}


def test_resolve_task_domain_prefers_known_canonical():
    known = ["脑肿瘤分割", "图像分割"]
    assert resolve_task_domain("脑肿瘤分割与图像合成", known) == "脑肿瘤分割"
    assert resolve_task_domain("图像分割", known) == "图像分割"
    assert resolve_task_domain("目标检测", known) == "目标检测"


def test_merge_extraction_batches_votes_normalized_domain():
    known = ["脑肿瘤分割"]
    merged = merge_extraction_batches(
        [
            {"task_domain": "脑肿瘤分割与图像合成", "raw_entities": [], "relations_raw": []},
            {"task_domain": "脑肿瘤分割", "raw_entities": [], "relations_raw": []},
        ],
        known_task_domains=known,
    )
    assert merged["task_domain"] == "脑肿瘤分割"
