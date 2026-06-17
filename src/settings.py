"""
ChronoPaper 统一配置入口。
所有 API Key、数据库连接、密钥均从项目根目录 .env 读取，代码中禁止硬编码。
"""
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
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
    zhipuai_api_key: str = ""
    dashscope_api_key: str = ""
    siliconflow_api_key: str = ""
    qianfan_access_key: str = ""
    qianfan_secret_key: str = ""
    ollama_api_base: str = "http://localhost:11434/v1/"
    ollama_api_key: str = "ollama"
    model_local_dir: str = "local"

    # --- MySQL ---
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_host: str = "localhost"
    mysql_db: str = "chronopaper"

    # --- Neo4j（主库，graphbase 使用）---
    neo4j_uri: str = "neo4j://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = ""

    # --- Neo4j Legacy（data_router 图谱上传，默认同主库）---
    neo4j_legacy_uri: str = ""
    neo4j_legacy_username: str = "neo4j"
    neo4j_legacy_password: str = ""

    # --- Milvus ---
    milvus_uri: str = "http://localhost:19530"
    milvus_token: str = ""
    milvus_db_name: str = "default"

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

    @property
    def neo4j_legacy_uri_resolved(self) -> str:
        return self.neo4j_legacy_uri or self.neo4j_uri

    @property
    def neo4j_legacy_password_resolved(self) -> str:
        return self.neo4j_legacy_password or self.neo4j_password

    def mysql_url(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}/{self.mysql_db}?charset=utf8"
        )

    def milvus_config(self) -> dict:
        return {
            "uri": self.milvus_uri,
            "token": self.milvus_token,
            "db_name": self.milvus_db_name,
        }

    def neo4j_config(self) -> dict:
        return {
            "uri": self.neo4j_uri,
            "username": self.neo4j_username,
            "password": self.neo4j_password,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
