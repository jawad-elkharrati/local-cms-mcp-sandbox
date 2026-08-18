from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class MCPSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    blog_api_base_url: str = "http://127.0.0.1:8000/api/v1"
    blog_api_token: str = "dev-editor-token"  # noqa: S105 - deliberately fake
    mcp_transport: Literal["stdio", "streamable-http"] = "stdio"
    mcp_http_host: str = "127.0.0.1"
    mcp_http_port: int = 8100
    content_similarity_engine: Literal["tfidf"] = "tfidf"
    local_embedding_model_path: str = "./models/local-embedding-model"

    @field_validator("mcp_http_host")
    @classmethod
    def localhost_only(cls, value: str) -> str:
        if value not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("MCP HTTP must bind to loopback only")
        return value

    @field_validator("blog_api_base_url")
    @classmethod
    def local_api_only(cls, value: str) -> str:
        allowed = ("http://127.0.0.1", "http://localhost", "http://fake-blog")
        if not value.startswith(allowed):
            raise ValueError("Fake Blog API URL must be local")
        return value.rstrip("/")


@lru_cache
def get_settings() -> MCPSettings:
    return MCPSettings()
