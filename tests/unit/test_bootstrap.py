import pytest
from pydantic import ValidationError

from apps.fake_blog.settings import Settings
from apps.mcp_server.settings import MCPSettings
from packages.contracts import ArticleStatus


def test_defaults_are_local_and_fake() -> None:
    api = Settings(_env_file=None)
    mcp = MCPSettings(_env_file=None)
    assert api.app_env in {"local", "test"}
    assert "dev-editor-token" == mcp.blog_api_token
    assert mcp.blog_api_base_url.startswith("http://127.0.0.1")
    assert ArticleStatus.DRAFT == "draft"


@pytest.mark.parametrize("host", ["0.0.0.0", "192.0.2.1"])
def test_mcp_http_rejects_non_loopback(host: str) -> None:
    with pytest.raises(ValidationError):
        MCPSettings(_env_file=None, mcp_http_host=host)


def test_mcp_rejects_remote_api() -> None:
    with pytest.raises(ValidationError):
        MCPSettings(_env_file=None, blog_api_base_url="https://example.invalid/api/v1")
