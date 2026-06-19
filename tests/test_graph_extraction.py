from src.services.graph.extraction import merge_extraction_batches, collect_entities_for_upsert


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
