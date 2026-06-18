"""抓取语义匹配：复用知识库同一套 Embedding 加载逻辑。"""
from __future__ import annotations

from src.config import Config
from src.integrations.llm.embedding import get_embedding_model
from src.utils.logging_config import setup_logger

logger = setup_logger("CrawlEmbedding")


def get_crawl_embedder():
    """与知识库共用 config.yaml 的 embed_model，但不依赖 enable_knowledge_base 开关。"""
    cfg = Config()
    model = get_embedding_model(cfg, ignore_kb_switch=True)
    if model is None:
        raise RuntimeError("Embedding 模型加载失败，请检查 embed_model 配置与 API Key")
    logger.info("Crawl embedder ready (shared): %s", cfg.embed_model)
    return model
