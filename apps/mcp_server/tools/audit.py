from typing import Any

from mcp.server import MCPServer

from apps.mcp_server.tools.articles import request
from apps.mcp_server.tools.common import safe


def register(mcp: MCPServer) -> None:
    @mcp.tool(name="get_audit_log")
    async def get_audit_log(
        action: str | None = None, entity_id: str | None = None, request_id: str | None = None
    ) -> dict[str, Any]:
        """Read allowed audit events."""
        return await safe(
            lambda: request(
                "GET",
                "/audit",
                params={"action": action, "entity_id": entity_id, "request_id": request_id},
            )
        )

    @mcp.tool(name="get_article_audit")
    async def get_article_audit(article_id: str) -> dict[str, Any]:
        """Read one article's traceable history."""
        return await safe(lambda: request("GET", f"/articles/{article_id}/audit"))
