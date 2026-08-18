from typing import Any

from mcp.server import MCPServer

from apps.mcp_server.tools.articles import request
from apps.mcp_server.tools.common import safe


def register(mcp: MCPServer) -> None:
    @mcp.tool(name="list_article_versions")
    async def list_article_versions(article_id: str) -> dict[str, Any]:
        """List immutable article revisions."""
        return await safe(lambda: request("GET", f"/articles/{article_id}/revisions"))

    @mcp.tool(name="get_article_version")
    async def get_article_version(article_id: str, version: int) -> dict[str, Any]:
        """Read an immutable historical snapshot."""
        return await safe(lambda: request("GET", f"/articles/{article_id}/revisions/{version}"))

    @mcp.tool(name="diff_article_versions")
    async def diff_article_versions(
        article_id: str, from_version: int, to_version: int
    ) -> dict[str, Any]:
        """Return structured and unified differences."""
        return await safe(
            lambda: request(
                "GET", f"/articles/{article_id}/revisions/{from_version}/diff/{to_version}"
            )
        )

    @mcp.tool(name="restore_article_version")
    async def restore_article_version(
        article_id: str, version: int, expected_version: int, confirm: bool = False
    ) -> dict[str, Any]:
        """Restore a snapshot as a new version after confirmation."""
        if not confirm:
            return {
                "ok": False,
                "error": {
                    "code": "confirmation_required",
                    "message": "Set confirm=true after reviewing the diff",
                },
            }
        return await safe(
            lambda: request(
                "POST",
                f"/articles/{article_id}/revisions/{version}/restore",
                json={"expected_version": expected_version},
            )
        )
