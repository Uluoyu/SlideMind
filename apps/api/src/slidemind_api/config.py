from pathlib import Path
from typing import Literal

from pydantic import Field
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
