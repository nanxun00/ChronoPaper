import tempfile

from src.api.deps import get_current_user
import os
from typing import List, Optional
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Body
from pydantic import BaseModel
from src.utils import setup_logger, hashstr
from src.services.rag.startup import startup
from src.settings import get_settings
from neo4j import GraphDatabase
import json
from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility, list_collections
from urllib.parse import urlparse
import shutil
from fastapi.responses import JSONResponse
import numpy as np
import pandas as pd
import csv
import fitz  # PyMuPDF
import docx
from io import StringIO, BytesIO
import openai
from minio import Minio
from minio.error import S3Error
import io
import shutil
data = APIRouter(prefix="/data")
router = data

logger = setup_logger("server-database")

@data.get("/")
def get_databases(
):
    '''
        获取系统中所有数据库的信息
        此函数尝试调用数据库管理模块的get_databases()方法来获取数据库的列表
        调用成功的话，直接赶回数据库的列表；如果调用失败的话，返回字典信息
    '''
    try:
        database = startup.dbm.get_databases()
    except Exception as e:
        return {"message": f"获取数据库列表失败 {e}", "databases": []}
    return database

@data.post("/")
async def create_database(
    database_name: str = Body(...),
    description: str = Body(...),
    db_type: str = Body(...),
    dimension: Optional[int] = Body(None),
):
    '''
        创建数据库的接口

        该异步函数通过post请求创建一个新的数据库，并返回数据库的相关信息
        参数：
            - database_name(str)：数据库的名称，必填
            - description(str)：数据库的描述信息，必填
            - db_type(str)：数据库的类型，必填
            - dimension(optional[int])：数据库的维度，可选
        返回：
            - database_info: 新创建数据库的信息
    '''
    # 调用创建数据库的日志信息
    logger.debug(f"Create database {database_name}")
    # 调用数据库管理器的创建数据库的方法，并传入相关参数
    database_info = startup.dbm.create_database(
        database_name,
        description,
        db_type,
        dimension=dimension
    )
    return database_info

@data.delete("/")
async def delete_database(db_id,
                          ):
    '''
        异步删除指定的数据库
        该函数用于处理特定数据库的请求，其中db_id是要删除的数据库的唯一标识符
        函数首先记录一条调试信息，表明即将删除哪个数据库，然后调用startup.dbm.delete_database()方法执行删除操作
        操作成功后，返回删除成功的消息

        参数：
            - db_id：要删除数据库的唯一标识符
        返回值：
            - 包含表示删除结果的消息的字典，消息内容为：“删除成功”
    '''
    logger.debug(f"Delete database {db_id}")
    startup.dbm.delete_database(db_id)
    return {"message": "删除成功"}

@data.post("/query-test")
async def query_test(query: str = Body(...), meta: dict = Body(...),
                     ):
    '''
        异步端点，用于查询知识库数据

        该函数接受一个查询字符串和一个元数据字典作为输入，记录查询信息
        然后调用startup.retriever.query_knowledgebase方法来处理查询
        最后返回查询结果

        参数：
            - query(str): 查询字符串，由客户端请求体提供
            - meta(dict): 额外的元数据，由客户端通过请求体提供，用于为查询提供更多的上下文

        返回值：
            - result: 查询知识库的结果，具体类型取决于query_knowledgebase方法体的实现
    '''
    logger.debug(f"Query test in {meta}: {query}")
    result = startup.retriever.query_knowledgebase(query, history=None, refs={"meta": meta})
    return result

@data.post("/add-by-file")
async def create_document_by_file(db_id: str = Body(...), files: List[str] = Body(...),
                                  ):
    '''
        通过文件创建文档
        改短点允许用户通过post请求上传文件来创建文档。他接受数据库id和一个文件列表作为参数
        参数：
        - db_id(str)：数据库的唯一标识符。这是从请求体中提取的
        - files(List[str])：用户想要添加的文件路径列表。这是从请求体中提取的
        返回：
        - msg: 表示文件添加操作结果的消息
    '''
    logger.debug(f"Add document in {db_id} by file: {files}")
    msg = startup.dbm.add_files(db_id, files)
    return msg

@data.get("/info")
async def get_database_info(db_id: str,
                            ):
    '''
    获取指定数据库的信息
    参数：
        - db_id(str)：数据库的唯一标识符
    返回：
        - database：数据库信息，如果找不到指定的数据库，则抛出404异常
    '''
    logger.debug(f"Get database {db_id} info")
    database = startup.dbm.get_database_info(db_id)
    if database is None:
        raise HTTPException(status_code=404, detail="Database not found")
    return database

@data.delete("/document")
async def delete_document(db_id: str = Body(...), file_id: str = Body(...)):
    '''
        异步处理删除文档请求的函数
        该函数接收数据库ID（db_id)和文件ID（file_id）作为参数
        并在数据库中删除指定的文档信息

        参数：
        - db_id(str)： 数据库的唯一标识符
        - file_id(str)：需要删除的文件的唯一标识符
        返回：
        - 一个包含消息的字典，表示删除操作的结果
    '''
    logger.debug(f"DELETE document {file_id} info in {db_id}")
    startup.dbm.delete_file(db_id, file_id)
    return {"message": "删除成功"}

@data.get("/papers")
async def list_kb_papers(
    db_id: str,
    page: int = 1,
    page_size: int = 20,
    q: str | None = None,
):
    """列出知识库中已向量入库的文献（按 paper_id 关联的 text_chunks）。"""
    logger.debug(f"List indexed papers in {db_id}, page={page}")
    return startup.dbm.list_indexed_papers(db_id, page=page, page_size=page_size, q=q)


@data.get("/document")
async def get_document_info(
    db_id: str,
    file_id: str | None = None,
    paper_id: str | None = None,
):
    '''
        异步函数获取文档信息
        该函数通过接受数据库ID和文件ID作为参数，查询并返回指定文档的信息。它使用了装饰器来处理HTTP get请求
        并且在遇到错误时记录错误信息并但会失败的响应
        参数：
        - db_id(str)：数据库ID，用于指定查询的数据库
        - file_id(str)：文件ID，用于指定查询的文件
        返回：
        - info: 文档信息的字典，如果查询失败，则返回包含错误信息和状态码的字典
    '''
    logger.debug(f"GET document in {db_id}, file_id={file_id}, paper_id={paper_id}")

    if not file_id and not paper_id:
        raise HTTPException(status_code=400, detail="file_id 或 paper_id 必填其一")

    try:
        if paper_id:
            info = startup.dbm.get_paper_chunks(db_id, paper_id)
        else:
            info = startup.dbm.get_file_info(db_id, file_id)
    except Exception as e:
        logger.error(f"Failed to get file info, {e}, {db_id=}, {file_id=}")
        info = {"message": "Failed to get file info", "status": "failed"}, 500

    return info


# @data.post("/upload")
# async def upload_file(file: UploadFile = File(...)):
#     '''
#         处理文件上传的异步函数
#         该函数接受一个上传的文件，验证文件是否存在，生成唯一文件名
#         将文件保存到指定目录，并返回成功消息和文件路径
#         参数：
#             - file：UploadFile - 要上传的文件，类型为UploadFile
#         返回：
#             - 包含成功消息和保存文件路径的字典
#     '''
#     if not file.filename:
#         raise HTTPException(status_code=400, detail="No selected file")
#
#     UPLOAD_DIR = r"src/saves/pdf2txt"
#     os.makedirs(UPLOAD_DIR, exist_ok=True)
#     basename, ext = os.path.splitext(file.filename)
#     # print(basename)
#     # 使用原始文件名和哈希值生成唯一的文件名，以避免文件的覆盖
#     filename = f"{basename}_{os.urandom(8).hex()}{ext}"
#     # 组合上传目录和文件名以形成完整的文件路径
#     file_path = f'{UPLOAD_DIR}/{filename}'
#
#     # with open(file_path, "wb") as buffer:
#     #       shutil.copyfileobj(file.file, buffer)
#     # 以二进制写模式打开文件路径，并将上传的文件内容写入该文件
#     with open(file_path, "wb") as buffer:
#         buffer.write(await file.read())
#     # print(file_path)
#     return {"message": "File successfully uploaded", "file_path": file_path}

# 处理文件上传的异步函数
@data.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    处理文件上传的异步函数
    该函数接受一个上传的文件，验证文件是否存在，生成唯一文件名
    将文件保存到指定目录，并返回成功消息和文件路径
    参数：
        - file：UploadFile - 要上传的文件，类型为UploadFile
    返回：
        - 包含成功消息和保存文件路径的字典
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No selected file")

    # 使用原始文件名和哈希值生成唯一的文件名，以避免文件的覆盖
    basename, ext = os.path.splitext(file.filename)
    filename = f"{basename}_{os.urandom(8).hex()}{ext}"
    # 组合上传目录和文件名以形成完整的文件路径
    file_path = os.path.join(UPLOAD_DIR, filename)

    # 使用临时文件和流式写入处理大文件
    try:
        # 创建临时文件对象
        with tempfile.NamedTemporaryFile(delete=False, mode='wb', suffix=ext) as temp_file:
            # 保存临时文件路径
            temp_file_path = temp_file.name

            # 流式写入文件内容
            chunk_size = 1024 * 1024  # 1MB分块
            while content := await file.read(chunk_size):
                temp_file.write(content)

        # 移动临时文件到目标位置（使用临时文件对象的 name 属性）
        shutil.move(temp_file_path, file_path)

        return {"message": "File successfully uploaded", "file_path": file_path}
    except Exception as e:
        # 发生错误时返回错误信息
        return JSONResponse(
            status_code=500,
            content={"message": f"File upload failed: {str(e)}"}
        )
    finally:
        # 确保关闭文件
        await file.close()

@data.get("/graph")
async def get_graph_info():
    '''
        获取图形信息
        返回：
            graph_info: 图形信息，其内容和格式取决于方法的实现
    '''
    graph_info = startup.dbm.get_graph()
    return graph_info

@data.get("/graph/node/")
async def get_graph_node(entity_name: str|None=None):
    '''
        异步获取图形数据库中指定实体名称的节点信息
        参数：
            - entity_name(str)：要查询的实体名称
        返回：
            - dict: 包含查询结果和状态消息的字典
    '''
    if entity_name:
        logger.debug(f"Get graph node {entity_name}")
        # 指定查询操作，获取指定实体名称的节点信息
        result = startup.dbm.graph_base.query_node(entity_name=entity_name)
        return {"result": startup.retriever.format_query_results(result), "message": "success"}
    else:
        result = startup.dbm.graph_base.get_sample_nodes("neo4j", "10000")
        return {"result": startup.retriever.format_general_results(result), "message": "success"}

@data.get("/graph/nodes")
async def get_graph_nodes(kgdb_name: str, num: int, include_cite: bool = True):
    '''
        获取知识图谱的节点信息
        主要用于展示或分析知识图谱的数据结构
        参数:
        - kgdb_name(str)：知识图谱数据库的名称
        - num(int)：要获取的节点的数量，表示返回的节点示例数量
        返回：
        返回一个包含节点信息的字典，以及一个表示操作状态的消息
    '''
    # 检查是够启用了包含节点信息的字典，如果没有，抛出异常
    if not startup.config.enable_knowledge_graph:
        raise HTTPException(status_code=400, detail="Knowledge graph is not enabled")

    logger.debug(f"Get graph nodes in {kgdb_name} with {num} nodes include_cite={include_cite}")
    result = startup.dbm.graph_base.get_sample_nodes(kgdb_name, num, include_cite=include_cite)
    return {"result": startup.retriever.format_general_results(result), "message": "success"}


@data.get("/graph/task-domains")
async def get_graph_task_domains(kgdb_name: str = "neo4j", limit: int = 50):
    """返回知识库图谱中已索引论文的领域列表（供前端筛选）。"""
    if not startup.config.enable_knowledge_graph:
        raise HTTPException(status_code=400, detail="Knowledge graph is not enabled")

    store = startup.dbm.graph_store
    if not store:
        return {"domains": [], "message": "graph store unavailable"}

    kb_id = startup.dbm.get_default_public_kb_id()
    if not kb_id:
        return {"domains": [], "message": "no knowledge base"}

    domains = store.list_task_domains(
        kb_id=kb_id,
        user_id=0,
        limit=max(1, min(int(limit), 100)),
    )
    return {"domains": domains, "message": "success"}

@data.post("/graph/add")
async def add_graph_entity(file_path: str = Body(...), kgdb_name: Optional[str] = Body(None)):
    raise HTTPException(
        status_code=410,
        detail="Legacy graph upload removed. Graph is built automatically after paper indexing.",
    )




# Neo4j 连接服务
class Neo4jService:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def get_session(self):
        return self.driver.session()
    def insert_triplet(self, h, r, t):
        query = """
           MERGE (h:Entity {name: $h})
           MERGE (t:Entity {name: $t})
           MERGE (h)-[:`$r`]->(t)
           """
        with self.driver.session() as session:
            session.run(query, h=h, r=r, t=t)
    def get_triplets(self):
        query = """
        MATCH (h:Entity)-[r]->(t:Entity)
        RETURN h.name AS subject, type(r) AS relationship, t.name AS target
        """
        with self.driver.session() as session:
            result = session.run(query)
            return [dict(record) for record in result]

    def delete_triplet(self, h,r,t):
        # 删除指定关系
        query = """
        MATCH (h:Company {name: $h})-[r]->(t:Company {name: $t})
        DELETE r
        """
        session = self.get_session()
        session.run(query, h=h, t=t)
        session.close()
        self.delete_node_if_orphan(h)
        self.delete_node_if_orphan(t)

    def delete_node_if_orphan(self, node_name):
        # 删除孤立节点：只有在没有任何关系指向它时，才删除该节点
        query = """
        MATCH (n:Company {name: $node_name})
        OPTIONAL MATCH (n)-[r]->()
        OPTIONAL MATCH ()-[r]->(n)
        DELETE r
        RETURN count(n) as node_count
        """
        session = self.get_session()
        result = session.run(query, node_name=node_name)
        count = result.single()["node_count"]
        session.close()
        if count == 0:  # 如果没有关系指向该节点，则删除该节点
            query_delete_node = """
            MATCH (n:Company {name: $node_name})
            DETACH DELETE n
            """
            session = self.get_session()
            session.run(query_delete_node, node_name=node_name)
            session.close()

    def delete_node(self, h):
        # 强制删除节点及其所有关系
        query = """
        MATCH (n:Company {name: $h})
        DETACH DELETE n
        """
        session = self.get_session()
        session.run(query, h=h)
        session.close()

    def delete_all_data_from_file(self, file_path):
        """从文件中读取并删除所有相关的三元组数据"""
        with open(file_path, "r", encoding="utf-8") as file:
            for line in file:
                data = json.loads(line)
                h, r, t = data["h"], data["r"], data["t"]
                self.delete_triplet(h, r, t)

        print(f"Data from {file_path} deleted successfully.")

    def delete_all(self):
        query = """
        MATCH (n)
        DETACH DELETE n
        """
        session = self.get_session()
        session.run(query)

    def delete_node_by_name(self, name: str):
        query = """
        MATCH (n {name: $name})
        DETACH DELETE n
        RETURN count(n) AS deleted_count
        """
        with self.driver.session() as session:
            result = session.run(query, name=name)
            return result.single()["deleted_count"]

_settings = get_settings()
neo4j_service = Neo4jService(
    _settings.neo4j_legacy_uri_resolved,
    _settings.neo4j_legacy_username,
    _settings.neo4j_legacy_password_resolved,
)


# Milvus 连接服务
class MilvusService:
    def __init__(self, collection_name="triplets"):
        self.collection_name = collection_name
        self.dim = 128  # 向量维度
        self.enabled = True

        # 从全局配置读取 milvus.uri 与 token
        milvus_cfg = getattr(startup.config, 'milvus', None) or {}
        uri = milvus_cfg.get('uri', '') or ''
        token = milvus_cfg.get('token', '') or ''

        # 根据 URI 决定使用方式
        if uri.startswith('http'):
            # 当前类基于 pymilvus gRPC 接口；HTTP/Serverless 请使用基于 MilvusClient 的实现
            print(f"Detected HTTP Milvus URI: {uri}. This gRPC-based MilvusService is disabled. Use REST MilvusClient elsewhere.")
            self.enabled = False
            return

        # 兼容 host:port 或 grpc://host:port
        if uri:
            parsed = urlparse(uri if '://' in uri else f"tcp://{uri}")
            host = parsed.hostname or 'localhost'
            port = str(parsed.port or 19530)
        else:
            # 回退：若未配置则使用本地默认端口
            host, port = 'localhost', '19530'

        self.connect_to_milvus(host, port)

        if self.collection_name not in list_collections():
            print(f"Collection '{self.collection_name}' does not exist. Creating it...")
            self.create_collection()
        else:
            print(f"Collection '{self.collection_name}' already exists.")

        self.collection = Collection(self.collection_name)
        self.create_index()
        self.collection.load()

    def connect_to_milvus(self, host, port):
        """连接到 Milvus 服务器"""
        try:
            connections.connect("default", host=host, port=port)
            print(f"Successfully connected to Milvus at {host}:{port}")
        except Exception as e:
            print(f"Error connecting to Milvus: {e}")
            raise

    def create_index(self):
        """为 embedding 字段创建索引"""
        index_params = {
            "index_type": "IVF_FLAT",  # 可改为 HNSW / IVF_PQ 等
            "metric_type": "L2",  # L2 距离
            "params": {"nlist": 128}  # nlist 越大，搜索精度越高，推荐 4 * sqrt(数据量)
        }
        self.collection.create_index("embedding", index_params)
    def create_collection(self):
        """创建集合"""
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dim),  # 向量维度 = 128
            FieldSchema(name="metadata", dtype=DataType.VARCHAR, max_length=1024)
        ]
        schema = CollectionSchema(fields, description="Triplet data schema")
        collection = Collection(name=self.collection_name, schema=schema)
        collection.load()  # 让 Collection 可用

    def insert_vector(self, vector, metadata):
        if not self.enabled:
            raise HTTPException(status_code=503, detail="Milvus (gRPC) 未启用：检测到 HTTP/Serverless URI，请使用 REST 客户端功能")
        if not isinstance(vector, list):
            raise ValueError(f"Embedding vector must be a list, but got {type(vector)}")

        if len(vector) != self.dim:
            raise ValueError(f"Embedding vector length must be {self.dim}, but got {len(vector)}")

        if isinstance(metadata, dict):
            metadata = json.dumps(metadata)  # 处理 metadata 格式

        if not isinstance(metadata, str):
            raise ValueError("Metadata must be a string or a dictionary that can be converted to JSON.")

        self.collection.insert([[vector], [metadata]])
        print("Data inserted successfully!")

def process_jsonl_file(filepath, neo4j_service, milvus_service):
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            h, r, t = data["h"], data["r"], data["t"]
            neo4j_service.insert_triplet(h, r, t)
            vector_h = np.random.rand(128).tolist()
            vector_t = np.random.rand(128).tolist()
            vector_r = np.random.rand(128).tolist()

            # 向量化并存入 Milvus
            milvus_service.insert_vector(vector_h, {"entity": h, "type": "h"})
            milvus_service.insert_vector(vector_t, {"entity": t, "type": "t"})
            milvus_service.insert_vector(vector_r, {"entity": r, "type": "r"})

milvus_service = MilvusService()
UPLOAD_DIR = "src/saves/data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 上传文件并处理
@data.post("/graph/upload")
async def upload_file(file: UploadFile = File(...)):
    raise HTTPException(
        status_code=410,
        detail="Legacy graph upload removed. Graph is built automatically after paper indexing.",
    )


# 获取图数据
@data.get("/graph/visualize/")
async def visualize_data():
    triplets = neo4j_service.get_triplets()
    return {"triplets": triplets}


# 删除文件
@data.delete("/graph/delete/{filename}")
async def delete_file(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        return {"filename": filename, "status": "deleted"}
    return {"error": "File not found"}

@data.delete("/delete/neo4j/{filename}")
async def delete_neo4j_data(filename:str):
    file_path = os.path.join(UPLOAD_DIR,filename)
    try:
        neo4j_service.delete_all_data_from_file(file_path)
        return {"message": f"All data from {filename} deleted successfully from Neo4j."}
    except Exception as e:
        return {"error": str(e)}
    finally:
        os.remove(file_path)

@data.delete("/delete/all_graph")
async def delete_all_graph():
    neo4j_service.delete_all()
    return {"message": "All graph data deleted successfully!"}

@data.delete("/delete/neo4j/entity")
async def delete_neo4j_entity(entity: str):
    neo4j_service.delete_node_by_name(entity)
    return {"message": f"Entity {entity} deleted successfully!"}


class NodeRequest(BaseModel):
    name: str  # 需要删除的节点名称


def delete_node_by_name(tx, name: str):
    query = """
    MATCH (n {name: $name})
    DETACH DELETE n
    RETURN count(n) AS deleted_count
    """
    result = tx.run(query, name=name)
    return result.single()["deleted_count"]


@data.delete("/graph/delete/node/")
def delete_node(entity: str):
    deleted_count = neo4j_service.delete_node_by_name(entity)

    if deleted_count == 0:
        raise HTTPException(status_code=404, detail="Node not found")

    return {"message": "Node deleted successfully", "name": entity}

######## 实体关系抽取 ########

def _get_openai_client():
    return openai.OpenAI(
        api_key=_settings.openai_api_key,
        base_url=_settings.openai_api_base,
    )


def extract_entities_and_relations(text):
    prompt = f"""
    请从以下文本中抽取出 "实体" 和 "实体之间的关系"，并返回 JSON 格式：
    - 实体可以是 人名、地名、机构名、产品、事件等
    - 关系描述实体间的联系，如 "隶属于"、"位于"、"生产"、"合作" 等

    示例：
    输入文本：
    "华为技术有限公司和中兴通讯股份有限公司是直接竞争对手；而中兴通讯股份有限公司和烽火通信科技股份有限公司则是间接竞争对手。烽火通信科技股份有限公司与华为技术有限公司是合作伙伴。
腾讯控股有限公司与阿里巴巴集团控股有限公司是直接竞争对手，而阿里巴巴集团控股有限公司与京东集团股份有限公司是间接竞争对手。京东集团股份有限公司与腾讯控股有限公司则是战略合作伙伴。
百度在线网络技术（北京）有限公司与字节跳动有限公司是直接竞争对手；字节跳动有限公司和快手科技有限公司是间接竞争对手。快手科技有限公司与百度在线网络技术（北京）有限公司是内容合作伙伴。
小米科技有限责任公司与OPPO广东移动通信有限公司是直接竞争对手；OPPO广东移动通信有限公司与维沃移动通信有限公司是间接竞争对手。维沃移动通信有限公司和小米科技有限责任公司则是供应链合作伙伴。
网易公司与新浪公司是直接竞争对手；新浪公司与搜狐公司是间接竞争对手。搜狐公司和网易公司是内容合作伙伴。
美团点评与饿了么是直接竞争对手；饿了么与百度外卖是间接竞争对手。百度外卖和美团点评是战略合作伙伴。
滴滴出行与曹操出行是直接竞争对手；曹操出行与首汽约车是间接竞争对手。首汽约车和滴滴出行是合作伙伴。
拼多多与唯品会是直接竞争对手；唯品会和蘑菇街是间接竞争对手。蘑菇街和拼多多是供应链合作伙伴。
蚂蚁集团与京东数科是直接竞争对手；京东数科与腾讯金融科技是间接竞争对手。腾讯金融科技和蚂蚁集团是战略合作伙伴。"

    输出 JSON：hao 
[
    {{"h":"华为技术有限公司","t":"中兴通讯股份有限公司","r":"直接竞争对手"}},
    {{"h":"烽火通信科技股份有限公司","t":"华为技术有限公司","r":"合作伙伴"}},
    {{"h":"腾讯控股有限公司","t":"阿里巴巴集团控股有限公司","r":"直接竞争对手"}},
    {{"h":"阿里巴巴集团控股有限公司","t":"京东集团股份有限公司","r":"间接竞争对手"}},
    {{"h":"京东集团股份有限公司","t":"腾讯控股有限公司","r":"战略合作伙伴"}},
    {{"h":"百度在线网络技术（北京）有限公司","t":"字节跳动有限公司","r":"直接竞争对手"}},
    {{"h":"字节跳动有限公司","t":"快手科技有限公司","r":"间接竞争对手"}},
    {{"h":"快手科技有限公司","t":"百度在线网络技术（北京）有限公司","r":"内容合作伙伴"}},
    {{"h":"小米科技有限责任公司","t":"OPPO广东移动通信有限公司","r":"直接竞争对手"}},
    {{"h":"OPPO广东移动通信有限公司","t":"维沃移动通信有限公司","r":"间接竞争对手"}},
    {{"h":"维沃移动通信有限公司","t":"小米科技有限责任公司","r":"供应链合作伙伴"}},
    {{"h":"网易公司","t":"新浪公司","r":"直接竞争对手"}},
    {{"h":"新浪公司","t":"搜狐公司","r":"间接竞争对手"}},
    {{"h":"搜狐公司","t":"网易公司","r":"内容合作伙伴"}},
    {{"h":"美团点评","t":"饿了么","r":"直接竞争对手"}},
    {{"h":"饿了么","t":"百度外卖","r":"间接竞争对手"}},
    {{"h":"百度外卖","t":"美团点评","r":"战略合作伙伴"}},
    {{"h":"滴滴出行","t":"曹操出行","r":"直接竞争对手"}},
    {{"h":"曹操出行","t":"首汽约车","r":"间接竞争对手"}},
    {{"h":"首汽约车","t":"滴滴出行","r":"合作伙伴"}},
    {{"h":"拼多多","t":"唯品会","r":"直接竞争对手"}},
    {{"h":"唯品会","t":"蘑菇街","r":"间接竞争对手"}},
    {{"h":"蘑菇街","t":"拼多多","r":"供应链合作伙伴"}},
    {{"h":"蚂蚁集团","t":"京东数科","r":"直接竞争对手"}},
    {{"h":"京东数科","t":"腾讯金融科技","r":"间接竞争对手"}},
    {{"h":"腾讯金融科技","t":"蚂蚁集团","r":"战略合作伙伴"}}
]   
    要求只输出json三元组，只展示结果，不要有额外的话
    现在，请处理以下文本：
    "{text}"
    """

    response = _get_openai_client().chat.completions.create(
        model="gpt-3.5-turbo",  # 使用最新 GPT-4 版本
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
    )

    output = response.choices[0].message.content
    try:
        result = json.loads(output)
    except Exception as e:
        result = output
    return result


# 读取 TXT 文件
def read_txt(file):
    return file.read().decode("utf-8")


# 读取 CSV 文件
def read_csv(file):
    content = file.read().decode("utf-8")
    reader = csv.DictReader(StringIO(content))
    return [row for row in reader]  # 解析为列表格式


# 读取 JSON 文件
def read_json(file):
    content = file.read().decode("utf-8")
    return json.loads(content)  # 解析 JSON


# 读取 Excel 文件（.xls/.xlsx）
def read_excel(file):
    df = pd.read_excel(BytesIO(file.read()))  # 读取 Excel
    return df.to_dict(orient="records")  # 转换为字典列表


# 读取 PDF 文件
def read_pdf(file):
    pdf_reader = fitz.open(stream=file.read(), filetype="pdf")  # 读取 PDF
    text = "\n".join(page.get_text() for page in pdf_reader)  # 提取所有页面文本
    return text.strip()  # 去除空格并返回


# 读取 Word (.docx) 文件
def read_word(file):
    doc = docx.Document(BytesIO(file.read()))  # 读取 Word 文件
    text = "\n".join([para.text for para in doc.paragraphs])  # 提取所有段落文本
    return text.strip()  # 去除空格并返回


@data.post("/graph/multi/upload/")
async def multi_upload_file(file: UploadFile = File(...)):
    raise HTTPException(
        status_code=410,
        detail="Legacy OneKE graph upload removed. Graph is built automatically after paper indexing.",
    )


