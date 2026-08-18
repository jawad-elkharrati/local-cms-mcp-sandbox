import httpx
import pytest

from apps.fake_blog.main import app
from apps.mcp_server.client import BlogApiClient
from apps.mcp_server.errors import BlogApiError
from apps.mcp_server.settings import MCPSettings


def local_client(token: str) -> BlogApiClient:
    return BlogApiClient(
        MCPSettings(
            _env_file=None,
            blog_api_base_url="http://localhost/api/v1",
            blog_api_token=token,
        ),
        transport=httpx.ASGITransport(app=app),
    )


@pytest.mark.anyio
async def test_typed_client_maps_permission_without_token_leak() -> None:
    async with local_client("dev-reader-token") as client:
        with pytest.raises(BlogApiError) as caught:
            await client.create_article({"title": "Reader cannot create"})
    result = caught.value.as_result()
    assert result["error"]["code"] == "forbidden"
    assert "dev-reader-token" not in str(result)


@pytest.mark.anyio
async def test_client_create_calls_http_api() -> None:
    async with local_client("dev-editor-token") as client:
        result = await client.create_article(
            {"title": "Client Boundary Contract Article", "slug": "client-boundary-contract"},
            "client-contract-key",
        )
    assert result["status"] == "draft"
    assert result["request_id"]
