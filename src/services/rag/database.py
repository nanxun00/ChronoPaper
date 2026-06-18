import os
import json
import time
from src.parsers import pdf_simple as pdf2txt
from src.utils import hashstr, setup_logger, is_text_pdf
from src.integrations.llm.embedding import get_embedding_model
from src.settings import get_settings

logger = setup_logger("DataBaseManager")


class DataBaseManager:

    def __init__(self, config=None) -> None:
        self.config = config
        settings = get_settings()
        self.database_path = settings.kb_registry_path(config.save_dir)
        self.embed_model = get_embedding_model(config)

        if self.config.enable_knowledge_base:
            from src.services.rag.knowledgebase import KnowledgeBase
            self.knowledge_base = KnowledgeBase(config, self.embed_model)
            if self.config.enable_knowledge_graph:
                from src.services.rag.graphbase import GraphDatabase
                self.graph_base = GraphDatabase(self.config, self.embed_model)
                self.graph_base.start()
            else:
                self.graph_base = None

        self.data = {"databases": [], "graph": {}}

        self._load_databases()
        self._update_database()
        if self.config.enable_knowledge_base:
            self._sync_local_collections()

    def _kb_dimension(self, db: "DataBaseLite") -> int | None:
        from src.config import EMBED_MODEL_INFO

        if db.dimension:
            return int(db.dimension)
        model = db.embed_model or self.config.embed_model
        info = EMBED_MODEL_INFO.get(model) or {}
        return info.get("dimension")

    def _sync_local_collections(self) -> None:
        """按本地 database.json 与 Milvus 对齐：有则复用，无则创建 collection。"""
        if not getattr(self, "knowledge_base", None):
            return

        for db in self.data["databases"]:
            dimension = self._kb_dimension(db)
            if not dimension:
                logger.warning(
                    "Skip Milvus sync for %s (%s): unknown embedding dimension",
                    db.metaname,
                    db.name,
                )
                continue
            try:
                created = self.knowledge_base.ensure_collection(db.metaname, dimension)
                if created:
                    logger.info(
                        "Provisioned Milvus collection %s for local knowledge base %r",
                        db.metaname,
                        db.name,
                    )
            except Exception as exc:
                logger.error(
                    "Failed to sync Milvus collection %s (%s): %s",
                    db.metaname,
                    db.name,
                    exc,
                )

    def _load_databases(self):
        """将数据库的信息保存到本地的文件里面"""
        if not os.path.exists(self.database_path):
            return

        with open(self.database_path, "r") as f:
            data = json.load(f)
            self.data = {
                "databases": [DataBaseLite(**db) for db in data["databases"]],
                "graph": data["graph"]
            }

        # 检查所有文件，如果出现状态是 processing 的，那么设置为 failed
        for db in self.data["databases"]:
            for file in db.files:
                if file["status"] == "processing" or file["status"] == "waiting":
                    file["status"] = "failed"

    def _save_databases(self):
        """将数据库的信息保存到本地的文件里面"""
        self._update_database()
        os.makedirs(os.path.dirname(self.database_path), exist_ok=True)
        with open(self.database_path, "w+") as f:
            json.dump({
                "databases": [db.to_dict() for db in self.data["databases"]],
                "graph": self.data["graph"]
            }, f, ensure_ascii=False, indent=4)

    def _update_database(self):
        self.id2db = {db.db_id: db for db in self.data["databases"]}
        self.name2db = {db.name: db for db in self.data["databases"]}
        self.metaname2db = {db.metaname: db for db in self.data["databases"]}

    def get_databases(self):
        self._update_database()
        assert self.config.enable_knowledge_base, "知识库未启用"
        self._sync_local_collections()

        remote_collections = set(self.knowledge_base.get_collection_names())
        local_metanames = {db.metaname for db in self.data["databases"]}
        missing = local_metanames - remote_collections
        if missing:
            logger.warning("Local knowledge bases still missing on Milvus: %s", sorted(missing))

        extra_remote = remote_collections - local_metanames
        if extra_remote:
            logger.debug("Milvus collections not registered in database.json: %s", sorted(extra_remote))

        for db in self.data["databases"]:
            dimension = self._kb_dimension(db)
            try:
                db.update(self.knowledge_base.get_collection_info(db.metaname, dimension=dimension))
            except Exception as exc:
                logger.warning("Failed to read Milvus collection %s: %s", db.metaname, exc)
                db.update({
                    "collection_name": db.metaname,
                    "row_count": 0,
                    "sync_error": str(exc),
                })

        return {"databases": [db.to_dict() for db in self.data["databases"]]}

    def get_graph(self):
        if self.config.enable_knowledge_graph:
            self.data["graph"].update(self.graph_base.get_database_info("neo4j"))
            return {"graph": self.data["graph"]}
        else:
            return {"message": "Graph base not enabled", "graph": {}}

    def create_database(self, database_name, description, db_type, dimension):
        from src.config import EMBED_MODEL_INFO
        dimension = dimension or EMBED_MODEL_INFO[self.config.embed_model]["dimension"]

        new_database = DataBaseLite(database_name,
                                    description,
                                    db_type,
                                    embed_model=self.config.embed_model,
                                    dimension=dimension)

        self.knowledge_base.add_collection(new_database.metaname, dimension)
        self.data["databases"].append(new_database)
        self._save_databases()
        return self.get_databases()

    def add_files(self, db_id, files, params=None):
        db = self.get_kb_by_id(db_id)

        if db.embed_model != self.config.embed_model:
            logger.error(f"Embed model not match, {db.embed_model} != {self.config.embed_model}")
            return {"message": f"Embed model not match, cur: {self.config.embed_model}", "status": "failed"}

        # Preprocessing the files to the queue
        new_files = []
        for file in files:
            new_file = {
                "file_id": "file_" + hashstr(file + str(time.time())),
                "filename": os.path.basename(file),
                "path": file,
                "type": file.split(".")[-1].lower(),
                "status": "waiting",
                "created_at": time.time()
            }
            db.files.append(new_file)
            new_files.append(new_file)

        from src.services.rag.indexing import chunk
        for new_file in new_files:
            file_id = new_file["file_id"]
            idx = self.get_idx_by_fileid(db, file_id)
            db.files[idx]["status"] = "processing"
            print("file_tyep, {}", new_file["type"])
            try:
                if new_file["type"] in ["pdf", "md", "txt", "doc", "docx"]:
                    print("11111111")
                    texts = self.read_text(new_file["path"])
                    nodes = chunk(texts, params=params)
                else:
                    print("22222222")
                    logger.info("不支持该类型文件解析")
                    # new_file["path"]
                    texts = self.read_text(new_file["path"])
                    nodes = chunk(texts, params=params)

                self.knowledge_base.add_documents(
                    docs=[node.text for node in nodes],
                    collection_name=db.metaname,
                    dimension=self._kb_dimension(db),
                    file_id=file_id)

                idx = self.get_idx_by_fileid(db, file_id)
                db.files[idx]["status"] = "done"

            except Exception as e:
                logger.error(f"Failed to add documents to collection {db.metaname}, {e}")
                idx = self.get_idx_by_fileid(db, file_id)
                db.files[idx]["status"] = "failed"

            self._save_databases()

        return {"message": "全部解析完成", "status": "success"}

    def get_database_info(self, db_id):
        db = self.get_kb_by_id(db_id)
        if db is None:
            return None
        dimension = self._kb_dimension(db)
        if dimension:
            self.knowledge_base.ensure_collection(db.metaname, dimension)
        db.update(self.knowledge_base.get_collection_info(db.metaname, dimension=dimension))
        return db.to_dict()

    def read_text(self, file, params=None):
        print("33333")
        support_format = [".pdf", ".txt", ".md", "doc", "docx"]
        logger.info(f"支持的文件类型 support_format: {support_format}")
        assert os.path.exists(file), "File not found"
        logger.info(f"Try to read file {file}")

        if not os.path.isfile(file):
            logger.error(f"Directory not supported now!")
            raise NotImplementedError("Directory not supported now!")

        if file.endswith(".pdf"):
            print("44444444")
            if is_text_pdf(file):
                from src.services.rag.filereader import pdfreader
                return pdfreader(file)
            else:
                from src.parsers import pdf_simple as pdf2txt
                return pdf2txt(file, return_text=True)

        else: # TODO 需要优化文件类型判断
            print("55555555")
            logger.info("txt、md、doc、docx文件加载")
            from src.services.rag.filereader import plainreader
            return plainreader(file)

        # else:
        #     logger.error(f"File format not supported, only support {support_format}")
        #     raise Exception(f"File format not supported, only support {support_format}")

    def delete_file(self, db_id, file_id):
        db = self.get_kb_by_id(db_id)
        file_idx_to_delete = self.get_idx_by_fileid(db, file_id)

        self.knowledge_base.client.delete(
            collection_name=db.metaname,
            filter=f"file_id == '{file_id}'"),

        del db.files[file_idx_to_delete]
        self._save_databases()

    def get_file_info(self, db_id, file_id):
        db = self.get_kb_by_id(db_id)
        if db is None:
            return {"message": "database not found"}, 404
        lines = self.knowledge_base.client.query(
            collection_name=db.metaname,
            filter=f"file_id == '{file_id}'",
            output_fields=["id", "text", "file_id", "hash"]
        )
        return {"lines": lines}

    def chunking(self, text, params=None):
        chunk_method = params.get("chunk_method", "fixed")
        chunk_size = params.get("chunk_size", 500)

        """将文本切分成固定大小的块"""
        chunks = []
        for i in range(0, len(text), chunk_size):
            chunks.append(text[i:i + chunk_size])
        return chunks

    def delete_database(self, db_id):
        db = self.get_kb_by_id(db_id)
        if db is None:
            return {"message": "database not found"}, 404

        self.knowledge_base.client.drop_collection(db.metaname)
        self.data["databases"] = [d for d in self.data["databases"] if d.db_id != db_id]
        self._save_databases()
        return {"message": "删除成功"}

    def get_kb_by_id(self, db_id):
        for db in self.data["databases"]:
            if db.db_id == db_id:
                return db
        return None

    def get_idx_by_fileid(self, db, file_id):
        for idx, f in enumerate(db.files):
            if f["file_id"] == file_id:
                return idx


class DataBaseLite:
    def __init__(self, name, description, db_type, dimension=None, **kwargs) -> None:
        self.name = name
        self.description = description
        self.db_type = db_type
        self.dimension = dimension
        self.db_id = kwargs.get("db_id", hashstr(name))
        self.metaname = kwargs.get("metaname", f"{db_type[:1]}{hashstr(name)}")
        self.metadata = kwargs.get("metadata", {})
        self.files = kwargs.get("files", [])
        self.embed_model = kwargs.get("embed_model", None)

    def id2file(self, file_id):
        for f in self.files:
            if f["file_id"] == file_id:
                return f
        return None

    def update(self, metadata):
        self.metadata = metadata

    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "db_type": self.db_type,
            "db_id": self.db_id,
            "embed_model": self.embed_model,
            "metaname": self.metaname,
            "metadata": self.metadata,
            "files": self.files,
            "dimension": self.dimension
        }

    def to_json(self):
        return json.dumps(self.to_dict(), ensure_ascii=False)

    def __str__(self):
        return self.to_json()