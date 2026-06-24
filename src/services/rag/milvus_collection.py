"""全局唯一 Milvus 集合 paper_text_chunk。"""
from __future__ import annotations

from pymilvus import DataType, MilvusClient, MilvusException

from src.utils.logging_config import setup_logger

logger = setup_logger("MilvusCollection")

PAPER_TEXT_CHUNK = "paper_text_chunk"


def get_embed_dimension(config) -> int:
    from src.config import EMBED_MODEL_INFO

    model = config.embed_model or "zhipu-embedding-3"
    info = EMBED_MODEL_INFO.get(model) or {}
    dim = info.get("dimension")
    if not dim:
        raise ValueError(f"Unknown embedding dimension for model {model}")
    return int(dim)


def ensure_paper_text_chunk(client: MilvusClient, dimension: int) -> None:
    """创建或校验全局集合；维度不一致时抛错（需人工迁移）。"""
    if client.has_collection(PAPER_TEXT_CHUNK):
        desc = client.describe_collection(PAPER_TEXT_CHUNK)
        fields = desc.get("fields") or []
        vec_dim = None
        for field in fields:
            if field.get("name") == "vec":
                params = field.get("params") or {}
                vec_dim = int(params.get("dim") or 0) or None
                break
        if vec_dim and vec_dim != dimension:
            raise RuntimeError(
                f"Milvus collection {PAPER_TEXT_CHUNK} dim={vec_dim}, "
                f"but current embed model requires dim={dimension}. "
                "Please migrate or drop the collection manually."
            )
        return

    schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
    schema.add_field("chunk_id", DataType.VARCHAR, is_primary=True, max_length=64)
    schema.add_field("vec", DataType.FLOAT_VECTOR, dim=dimension)
    schema.add_field("paper_id", DataType.VARCHAR, max_length=128)
    schema.add_field("doc_id", DataType.VARCHAR, max_length=64)
    schema.add_field("kb_id", DataType.VARCHAR, max_length=32)
    schema.add_field("resource_type", DataType.VARCHAR, max_length=16)
    schema.add_field("owner_user_id", DataType.INT64)
    schema.add_field("year", DataType.INT64)
    schema.add_field("ccf_rank", DataType.VARCHAR, max_length=8)
    schema.add_field("section_type", DataType.VARCHAR, max_length=32)
    schema.add_field("block_type", DataType.VARCHAR, max_length=32)
    schema.add_field("task_domain", DataType.VARCHAR, max_length=64)
    schema.add_field("keywords", DataType.ARRAY, element_type=DataType.VARCHAR, max_capacity=32, max_length=64)
    schema.add_field("text_hash", DataType.VARCHAR, max_length=64)

    index_params = client.prepare_index_params()
    index_params.add_index(field_name="vec", index_type="AUTOINDEX", metric_type="COSINE")

    try:
        client.create_collection(
            collection_name=PAPER_TEXT_CHUNK,
            schema=schema,
            index_params=index_params,
        )
        logger.info("Created Milvus collection %s dim=%s", PAPER_TEXT_CHUNK, dimension)
    except MilvusException as exc:
        if "already exist" in str(exc).lower():
            return
        raise
