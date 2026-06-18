import os

from src.config import EMBED_MODEL_INFO, RERANKER_LIST
from src.utils.logging_config import setup_logger
from src.utils import hashstr

logger = setup_logger("EmbeddingModel")

GLOBAL_EMBED_STATE = {}


def _load_flag_model():
    from FlagEmbedding import FlagModel

    return FlagModel


def _load_flag_reranker():
    from FlagEmbedding import FlagReranker

    return FlagReranker


class EmbeddingModel:
    """本地 BGE 模型封装（按需加载 FlagEmbedding，避免启动时拉取 torch/transformers）。"""

    def __init__(self, model_info, config, **kwargs):
        self.info = model_info
        model_name_or_path = handle_local_model(
            paths=config.model_local_paths,
            model_name=model_info["name"],
            default_path=model_info.get("default_path", None),
        )

        logger.info("Loading embedding model %s from %s", model_info["name"], model_name_or_path)
        FlagModel = _load_flag_model()
        self._model = FlagModel(
            model_name_or_path,
            query_instruction_for_retrieval=model_info.get("query_instruction", None),
            use_fp16=False,
            **kwargs,
        )
        logger.info("Embedding model %s loaded", model_info["name"])

    def encode(self, message):
        return self._model.encode(message)

    def encode_queries(self, queries):
        return self._model.encode_queries(queries)


class Reranker:
    """交叉编码 Reranker（按需加载 FlagEmbedding）。"""

    def __init__(self, config, **kwargs):
        assert config.reranker in RERANKER_LIST, (
            f"Unsupported Reranker: {config.reranker}, only support {RERANKER_LIST.keys()}"
        )

        model_name_or_path = handle_local_model(
            paths=config.model_local_paths,
            model_name=config.reranker,
            default_path=RERANKER_LIST[config.reranker],
        )

        logger.info("Loading Reranker model %s from %s", config.reranker, model_name_or_path)

        cache_dir = ""
        if os.getenv("MODEL_LOCAL_DIR"):
            cache_dir = os.getenv("MODEL_LOCAL_DIR")

        FlagReranker = _load_flag_reranker()
        self._model = FlagReranker(model_name_or_path, use_fp16=True, cache_dir=cache_dir, **kwargs)
        logger.info("Reranker model %s loaded", config.reranker)

    def compute_score(self, *args, **kwargs):
        return self._model.compute_score(*args, **kwargs)


class ZhipuEmbedding:

    def __init__(self, model_info, config) -> None:
        from zhipuai import ZhipuAI

        self.config = config
        self.model_info = model_info
        self.client = ZhipuAI(api_key=os.getenv("ZHIPUAI_API_KEY"))
        logger.info("Zhipu Embedding model loaded")
        self.query_instruction_for_retrieval = "为这个句子生成表示以用于检索相关文章："

    def predict(self, message):
        data = []
        batch_size = 20

        if len(message) > batch_size:
            global GLOBAL_EMBED_STATE
            task_id = hashstr(message)
            logger.info("Creating new state for process %s", task_id)
            GLOBAL_EMBED_STATE[task_id] = {
                "status": "in-progress",
                "total": len(message),
                "progress": 0,
            }

        for i in range(0, len(message), batch_size):
            if len(message) > batch_size:
                logger.info("Encoding %s to %s with %s messages", i, i + batch_size, len(message))
                GLOBAL_EMBED_STATE[task_id]["progress"] = i

            group_msg = message[i : i + batch_size]
            response = self.client.embeddings.create(
                model=self.model_info.get("default_path", None),
                input=group_msg,
            )

            data.extend([a.embedding for a in response.data])

        if len(message) > batch_size:
            GLOBAL_EMBED_STATE[task_id]["progress"] = len(message)
            GLOBAL_EMBED_STATE[task_id]["status"] = "completed"

        return data

    def encode(self, message):
        return self.predict(message)

    def encode_queries(self, queries):
        queries = [self.query_instruction_for_retrieval + query for query in queries]
        return self.predict(queries)


def _create_embedding_model(config):
    assert config.embed_model in EMBED_MODEL_INFO, (
        f"Unsupported embed model: {config.embed_model}, only support {EMBED_MODEL_INFO.keys()}"
    )

    if config.embed_model in ["bge-large-zh-v1.5"]:
        return EmbeddingModel(EMBED_MODEL_INFO[config.embed_model], config)

    if config.embed_model in ["zhipu-embedding-2", "zhipu-embedding-3"]:
        return ZhipuEmbedding(EMBED_MODEL_INFO[config.embed_model], config)

    raise ValueError(f"Unsupported embed model: {config.embed_model}")


_cached_embedder = None
_cached_embedder_name: str | None = None


def get_embedding_model(config, *, ignore_kb_switch: bool = False):
    """加载 Embedding 模型。

    - 知识库默认要求 enable_knowledge_base=True
    - 抓取语义匹配可传 ignore_kb_switch=True，与知识库共用同一 embed_model 配置
    """
    global _cached_embedder, _cached_embedder_name

    if not ignore_kb_switch and not config.enable_knowledge_base:
        return None

    model_name = config.embed_model or "zhipu-embedding-3"
    if _cached_embedder is not None and _cached_embedder_name == model_name:
        return _cached_embedder

    model = _create_embedding_model(config)
    _cached_embedder = model
    _cached_embedder_name = model_name
    return model


def handle_local_model(paths, model_name, default_path):
    model_path = paths.get(model_name, default_path)
    if os.getenv("MODEL_ROOT_DIR") and not os.path.isabs(model_path):
        model_path = os.path.join(os.getenv("MODEL_ROOT_DIR"), model_path)
    return model_path
