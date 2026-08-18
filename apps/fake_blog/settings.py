from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["local", "test"] = "local"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://cms_lab:cms_lab_password@postgres:5432/cms_lab"
    redis_url: str = "redis://redis:6379/0"
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin123"  # noqa: S105 - deliberately fake
    minio_bucket: str = "cms-media"
    minio_secure: bool = False
    preview_token: str = "local-preview-token"  # noqa: S105 - deliberately fake
    max_upload_bytes: int = 10 * 1024 * 1024

    @field_validator("app_env")
    @classmethod
    def local_profiles_only(cls, value: str) -> str:
        if value not in {"local", "test"}:
            raise ValueError("Only local and test profiles are permitted")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
