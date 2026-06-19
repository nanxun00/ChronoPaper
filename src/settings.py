"""
ChronoPaper 统一配置入口。
所有 API Key、数据库连接、密钥均从项目根目录 .env 读取，代码中禁止硬编码。
"""
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(ENV_FILE, override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM API ---
    openai_api_key: str = ""
    openai_api_base: str = "https://api.openai.com/v1"
    deepseek_api_key: str = ""
    translate_model: str = "deepseek-chat"
    zhipuai_api_key: str = ""
    dashscope_api_key: str = ""
    xfyun_app_id: str = ""
    xfyun_api_key: str = ""
    xfyun_api_secret: str = ""
    siliconflow_api_key: str = ""
    qianfan_access_key: str = ""
    qianfan_secret_key: str = ""
    ollama_api_base: str = "http://localhost:11434/v1/"
    ollama_api_key: str = "ollama"
    model_local_dir: str = "local"

    # --- MySQL（MYSQL_PROFILE=local|remote 切换）---
    mysql_profile: str = Field(default="local", validation_alias="MYSQL_PROFILE")

    mysql_local_user: str = Field(default="root", validation_alias=AliasChoices("MYSQL_LOCAL_USER", "MYSQL_USER"))
    mysql_local_password: str = Field(default="", validation_alias=AliasChoices("MYSQL_LOCAL_PASSWORD", "MYSQL_PASSWORD"))
    mysql_local_host: str = Field(default="127.0.0.1", validation_alias=AliasChoices("MYSQL_LOCAL_HOST", "MYSQL_HOST"))
    mysql_local_port: int = Field(default=3306, validation_alias=AliasChoices("MYSQL_LOCAL_PORT", "MYSQL_PORT"))
    mysql_local_db: str = Field(default="chronopaper", validation_alias=AliasChoices("MYSQL_LOCAL_DB", "MYSQL_DB"))

    mysql_remote_user: str = Field(default="", validation_alias="MYSQL_REMOTE_USER")
    mysql_remote_password: str = Field(default="", validation_alias="MYSQL_REMOTE_PASSWORD")
    mysql_remote_host: str = Field(default="", validation_alias="MYSQL_REMOTE_HOST")
    mysql_remote_port: int = Field(default=3306, validation_alias="MYSQL_REMOTE_PORT")
    mysql_remote_db: str = Field(default="chronopaper", validation_alias="MYSQL_REMOTE_DB")

    # --- Neo4j（主库，graphbase 使用）---
    neo4j_uri: str = "neo4j://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = ""

    # --- Neo4j Legacy（data_router 图谱上传，默认同主库）---
    neo4j_legacy_uri: str = ""
    neo4j_legacy_username: str = "neo4j"
    neo4j_legacy_password: str = ""

    # --- Milvus / 知识库 ---
    milvus_uri: str = "http://localhost:19530"
    milvus_token: str = ""
    milvus_db_name: str = "chronopaper"

    # --- Celery / Redis ---
    celery_broker_url: str = "redis://127.0.0.1:6379/0"
    celery_result_backend: str = "redis://127.0.0.1:6379/1"
    auto_start_celery_worker: bool = Field(default=True, validation_alias="AUTO_START_CELERY_WORKER")

    save_dir: str | None = None
    kb_database_json: str = ""
    enable_knowledge_base: bool | None = None
    enable_knowledge_graph: bool | None = None
    enable_semantic_scholar_cite: bool = True
    enable_reranker: bool | None = None
    enable_search_engine: bool | None = None
    embed_model: str | None = None
    reranker: str | None = None

    # --- MinIO（可选）---
    minio_endpoint: str = ""
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_secure: bool = False
    minio_bucket: str = "image"

    # --- JWT / AES ---
    jwt_secret_key: str = ""
    aes_key: str = ""
    aes_iv: str = ""
    token_expires_time: int = 43200
    token_default_expires_time: int = 15

    # --- 网关 ---
    gateway_time_out: int = 90

    # --- OpenAlex ---
    openalex_api_key: str = ""
    openalex_mailto: str = ""

    # --- MinerU PDF 解析 ---
    mineru_lang: str = "en"
    mineru_backend: str = ""  # 空=自动：有 GPU 用 hybrid-engine，否则 pipeline

    @field_validator("mysql_profile", mode="before")
    @classmethod
    def _normalize_mysql_profile(cls, value):
        if value is None:
            return "local"
        return str(value).strip().lower()

    def _ensure_mysql_remote_config(self) -> None:
        if self.mysql_profile != "remote":
            return
        missing = []
        if not self.mysql_remote_host:
            missing.append("MYSQL_REMOTE_HOST")
        if not self.mysql_remote_user:
            missing.append("MYSQL_REMOTE_USER")
        if not self.mysql_remote_password:
            missing.append("MYSQL_REMOTE_PASSWORD")
        if missing:
            raise ValueError(
                f"MYSQL_PROFILE=remote 时须在 .env 中配置: {', '.join(missing)}"
            )

    def _active_mysql(self) -> dict:
        self._ensure_mysql_remote_config()
        if self.mysql_profile == "remote":
            return {
                "user": self.mysql_remote_user,
                "password": self.mysql_remote_password,
                "host": self.mysql_remote_host,
                "port": self.mysql_remote_port,
                "db": self.mysql_remote_db,
            }
        return {
            "user": self.mysql_local_user,
            "password": self.mysql_local_password,
            "host": self.mysql_local_host,
            "port": self.mysql_local_port,
            "db": self.mysql_local_db,
        }

    @property
    def mysql_user(self) -> str:
        return self._active_mysql()["user"]

    @property
    def mysql_password(self) -> str:
        return self._active_mysql()["password"]

    @property
    def mysql_host(self) -> str:
        return self._active_mysql()["host"]

    @property
    def mysql_port(self) -> int:
        return int(self._active_mysql()["port"])

    @property
    def mysql_db(self) -> str:
        return self._active_mysql()["db"]

    def mysql_summary(self) -> str:
        cfg = self._active_mysql()
        return (
            f"profile={self.mysql_profile} "
            f"host={cfg['host']}:{cfg['port']} "
            f"db={cfg['db']} user={cfg['user']}"
        )

    @property
    def neo4j_legacy_uri_resolved(self) -> str:
        return self.neo4j_legacy_uri or self.neo4j_uri

    @property
    def neo4j_legacy_password_resolved(self) -> str:
        return self.neo4j_legacy_password or self.neo4j_password

    def mysql_url(self) -> str:
        from urllib.parse import quote_plus
        user = quote_plus(self.mysql_user)
        password = quote_plus(self.mysql_password)
        return (
            f"mysql+pymysql://{user}:{password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}?charset=utf8mb4"
        )

    def milvus_config(self) -> dict:
        return {
            "uri": self.milvus_uri,
            "token": self.milvus_token,
            "db_name": self.milvus_db_name,
        }

    def kb_registry_path(self, save_dir: str | None = None) -> str:
        """知识库本地登记表 database.json 路径。"""
        if self.kb_database_json.strip():
            p = Path(self.kb_database_json.strip())
            return str(p if p.is_absolute() else PROJECT_ROOT / p)
        base = save_dir or self.save_dir or "src/saves"
        return str(PROJECT_ROOT / base / "data" / "database.json")

    def neo4j_config(self) -> dict:
        return {
            "uri": self.neo4j_uri,
            "username": self.neo4j_username,
            "password": self.neo4j_password,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
