from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from slidemind_common.security import SecurityLevel


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SLIDEMIND_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/slidemind.db"
    storage_backend: Literal["local", "minio"] = "local"
    storage_root: Path = Path("data/storage")
    max_upload_mb: int = Field(default=25, ge=1, le=500)
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    security_clearance: SecurityLevel = SecurityLevel.CONFIDENTIAL
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "slidemind"
    minio_secret_key: str = "slidemind-local-development"
    minio_bucket: str = "ppt"
    minio_secure: bool = False
    renderer_url: str = "http://127.0.0.1:3001"
    renderer_timeout_seconds: int = Field(default=60, ge=1, le=300)
    ingestion_enabled: bool = True
    ingestion_poll_seconds: float = Field(default=1, ge=0.1, le=60)
    ingestion_lease_seconds: int = Field(default=120, ge=30, le=1800)
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_cache_dir: Path = Path(".cache/fastembed")
    embedding_threads: int = Field(default=2, ge=1, le=16)
    embedding_provider: Literal["local", "http"] = "local"
    embedding_url: str = "http://127.0.0.1:6068/v1/embeddings"
    embedding_dimensions: int = Field(default=1024, ge=1, le=8192)
    embedding_revision: str = ""
    embedding_api_key: SecretStr = SecretStr("")
    embedding_timeout_seconds: int = Field(default=30, ge=1, le=180)
    embedding_query_instruction: str = (
        "Given a query, retrieve relevant passages that answer the query"
    )
    reranker_url: str = ""
    reranker_model: str = ""
    reranker_input_format: Literal["plain", "qwen3"] = "plain"
    reranker_api_key: SecretStr = SecretStr("")
    reranker_timeout_seconds: int = Field(default=15, ge=1, le=60)
    reranker_min_score: float = Field(default=0.05, ge=0, le=1)
    chunk_size: int = Field(default=400, ge=100, le=1000)
    retrieval_min_similarity: float = Field(default=0.5, ge=0, le=1)
