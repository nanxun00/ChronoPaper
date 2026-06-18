import os

from src.integrations.llm.embedding import EmbeddingModel
from pymilvus import MilvusClient, MilvusException
from src.utils import setup_logger, hashstr
logger = setup_logger("KnowledgeBase")


class KnowledgeBase:

    def __init__(self, config=None, embed_model=None) -> None:
        self.config = config or {}
        assert embed_model, "embed_model=None"
        self.embed_model = embed_model

        self.client = None
        if not self.connect_to_milvus():
            raise ConnectionError("Failed to connect to Milvus")

    def connect_to_milvus(self):
        """
        连接到 Milvus 服务。
        使用配置中的 URI，如果没有配置，则使用默认值。
        """
        try:
            uri = self.config.milvus.get('uri', "http://localhost:19015")
            token = self.config.milvus.get('token', "")
            db_name = self.config.milvus.get('db_name', "")
            self.client = MilvusClient(
                uri=uri,
                token=token,
                db_name=db_name
            )
            # 可以添加一个简单的测试来确保连接成功
            self.client.list_collections()
            logger.info(f"Successfully connected to Milvus at {uri}")
            return True
        except MilvusException as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            return False

    def get_collection_names(self):
        return self.client.list_collections()

    def has_collection(self, collection_name: str) -> bool:
        return self.client.has_collection(collection_name=collection_name)

    def ensure_collection(self, collection_name: str, dimension: int) -> bool:
        """本地登记的知识库在 Milvus 上不存在时自动创建。返回是否新建。"""
        if self.has_collection(collection_name):
            return False
        self.client.create_collection(
            collection_name=collection_name,
            dimension=dimension,
        )
        logger.info("Created Milvus collection %s (dim=%s)", collection_name, dimension)
        return True

    def get_collections(self):
        collections_name = self.client.list_collections()
        collections = []
        for collection_name in collections_name:
            collection = self.get_collection_info(collection_name)
            collections.append(collection)

        return collections

    def get_collection_info(self, collection_name, dimension: int | None = None):
        logger.info(f"获取到collection_name：{collection_name}")
        if not self.has_collection(collection_name):
            if dimension:
                self.ensure_collection(collection_name, dimension)
            else:
                return {
                    "collection_name": collection_name,
                    "row_count": 0,
                    "missing": True,
                }
        collection = self.client.describe_collection(collection_name)
        collection.update(self.client.get_collection_stats(collection_name))
        return collection

    def add_collection(self, collection_name, dimension=None):
        if self.has_collection(collection_name):
            logger.warning(f"Collection {collection_name} already exists, drop it")
            self.client.drop_collection(collection_name=collection_name)

        self.client.create_collection(
            collection_name=collection_name,
            dimension=dimension,
        )

    def add_documents(self, docs, collection_name, dimension=None, **kwargs):
        """添加已经分块之后的文本"""
        import random
        if not self.has_collection(collection_name=collection_name):
            if not dimension:
                raise ValueError(f"Collection {collection_name} not found and dimension is required to create it")
            self.ensure_collection(collection_name, dimension)

        vectors = self.embed_model.encode(docs)

        data = [{
            "id": int(random.random() * 1e12),
            "vector": vectors[i],
            "text": docs[i],
            "hash": hashstr(docs[i], with_salt=True),
            **kwargs} for i in range(len(vectors))]

        res = self.client.insert(collection_name=collection_name, data=data)
        return res

    def search(self, query, collection_name, limit=3):

        query_vectors = self.embed_model.encode_queries([query])
        return self.search_by_vector(query_vectors[0], collection_name, limit)

    def search_by_vector(self, vector, collection_name, limit=3):
        res = self.client.search(
            collection_name=collection_name,  # target collection
            data=[vector],  # query vectors
            limit=limit,  # number of returned entities
            output_fields=["text", "file_id"],  # specifies fields to be returned
        )

        return res[0]

    def examples(self, collection_name, limit=20):
        res = self.client.query(
            collection_name=collection_name,
            limit=10,
            output_fields=["id", "text"],
        )
        return res

    def search_by_id(self, collection_name, id, output_fields=["id", "text"]):
        res = self.client.get(collection_name, id, output_fields=output_fields)
        return res
