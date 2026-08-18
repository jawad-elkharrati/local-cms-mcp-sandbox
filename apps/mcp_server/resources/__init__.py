import json
from typing import Any

from mcp.server import MCPServer

from apps.mcp_server.client import BlogApiClient


async def get(path: str) -> str:
    async with BlogApiClient() as client:
        return json.dumps(await client.get(path), indent=2, default=str)


def register_resources(mcp: MCPServer) -> None:
    @mcp.resource("cms://site/info", mime_type="application/json")
    async def site_info() -> str:
        """Local Fake Blog identity and capabilities."""
        return await get("/capabilities")

    @mcp.resource("cms://site/content-rules", mime_type="application/json")
    async def content_rules() -> str:
        """Publishing validation rules."""
        return json.dumps(
            {
                "title_length": [10, 80],
                "slug": "lowercase-kebab-case",
                "publish_min_words": 150,
                "deleted_article_can_publish": False,
                "taxonomy": "recommended",
                "featured_image": "warning",
            },
            indent=2,
        )

    @mcp.resource("cms://taxonomy/tags", mime_type="application/json")
    async def tags() -> str:
        return await get("/tags")

    @mcp.resource("cms://taxonomy/categories", mime_type="application/json")
    async def categories() -> str:
        return await get("/categories")

    @mcp.resource("cms://articles/{article_id}", mime_type="application/json")
    async def article(article_id: str) -> str:
        return await get(f"/articles/{article_id}")

    @mcp.resource("cms://articles/{article_id}/metadata", mime_type="application/json")
    async def article_metadata(article_id: str) -> str:
        data = json.loads(await get(f"/articles/{article_id}"))
        data.pop("content_markdown", None)
        data.pop("content_html", None)
        return json.dumps(data, indent=2, default=str)

    @mcp.resource("cms://articles/{article_id}/revisions", mime_type="application/json")
    async def revisions(article_id: str) -> str:
        return await get(f"/articles/{article_id}/revisions")

    @mcp.resource("cms://articles/{article_id}/revisions/{version}", mime_type="application/json")
    async def revision(article_id: str, version: str) -> str:
        return await get(f"/articles/{article_id}/revisions/{version}")

    @mcp.resource("cms://articles/{article_id}/audit", mime_type="application/json")
    async def audit(article_id: str) -> str:
        return await get(f"/articles/{article_id}/audit")

    @mcp.resource("cms://media/{media_id}", mime_type="application/json")
    async def media(media_id: str) -> str:
        data: dict[str, Any] = await _get_dict(f"/media/{media_id}")
        data["usage"] = await _get_dict(f"/media/{media_id}/usage")
        return json.dumps(data, indent=2, default=str)

    @mcp.resource("cms://docs/workflow", mime_type="text/markdown")
    async def workflow() -> str:
        return "# Local editorial workflow\n\nRead and analyze first. Create drafts only. Preview diffs, pass expected_version, validate, then request an explicit publish action with a publisher identity. Never escalate credentials."


async def _get_dict(path: str) -> dict[str, Any]:
    async with BlogApiClient() as client:
        return await client.get(path)
