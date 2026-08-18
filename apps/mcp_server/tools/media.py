from typing import Any

from mcp.server import MCPServer

from apps.mcp_server.client import BlogApiClient
from apps.mcp_server.tools.articles import request
from apps.mcp_server.tools.common import safe


def register(mcp: MCPServer) -> None:
    @mcp.tool(name="list_media")
    async def list_media() -> dict[str, Any]:
        """List local media metadata."""
        return await safe(lambda: request("GET", "/media"))

    @mcp.tool(name="get_media")
    async def get_media(media_id: str) -> dict[str, Any]:
        """Get local media metadata."""
        return await safe(lambda: request("GET", f"/media/{media_id}"))

    @mcp.tool(name="upload_media")
    async def upload_media(
        local_path: str, alt_text: str | None = None, caption: str | None = None
    ) -> dict[str, Any]:
        """Validate and upload a regular local file through the API."""

        async def call() -> dict[str, Any]:
            async with BlogApiClient() as client:
                return await client.upload_media(local_path, alt_text, caption)

        return await safe(call)

    @mcp.tool(name="update_media_metadata")
    async def update_media_metadata(
        media_id: str, alt_text: str | None = None, caption: str | None = None
    ) -> dict[str, Any]:
        """Update alt text or caption."""
        return await safe(
            lambda: request(
                "PATCH", f"/media/{media_id}", json={"alt_text": alt_text, "caption": caption}
            )
        )

    @mcp.tool(name="get_media_usage")
    async def get_media_usage(media_id: str) -> dict[str, Any]:
        """List articles referencing media."""
        return await safe(lambda: request("GET", f"/media/{media_id}/usage"))

    @mcp.tool(name="delete_media")
    async def delete_media(media_id: str, confirm: bool = False) -> dict[str, Any]:
        """Soft-delete unused media after confirmation."""
        if not confirm:
            return {
                "ok": False,
                "error": {"code": "confirmation_required", "message": "Set confirm=true"},
            }
        return await safe(lambda: request("DELETE", f"/media/{media_id}"))

    @mcp.tool(name="set_featured_media")
    async def set_featured_media(
        article_id: str, expected_version: int, media_id: str | None = None
    ) -> dict[str, Any]:
        """Set or clear the featured media."""
        return await safe(
            lambda: request(
                "PUT",
                f"/articles/{article_id}/featured-media",
                json={"expected_version": expected_version, "media_id": media_id},
            )
        )
