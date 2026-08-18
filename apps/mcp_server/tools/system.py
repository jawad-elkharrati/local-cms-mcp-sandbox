from typing import Any

from mcp.server import MCPServer

from apps.mcp_server.client import BlogApiClient
from apps.mcp_server.tools.common import safe


def register(mcp: MCPServer) -> None:
    @mcp.tool(name="whoami")
    async def whoami() -> dict[str, Any]:
        """Return the configured fictional API identity without its token."""
        return await safe(lambda: _get("/me"))

    @mcp.tool(name="health_check")
    async def health_check() -> dict[str, Any]:
        """Check the local Fake Blog and dependency health."""
        return await safe(lambda: _get("/health"))

    @mcp.tool(name="get_service_info")
    async def get_service_info() -> dict[str, Any]:
        """Return local-only MCP and Fake Blog service information."""
        result = await safe(lambda: _get("/capabilities"))
        return {
            "mcp_name": "local-cms-mcp-lab",
            "mcp_version": "0.1.0",
            "local_only": True,
            **result,
        }

    @mcp.tool(name="get_permissions")
    async def get_permissions() -> dict[str, Any]:
        """Return effective fake API scopes and permission hints."""
        return await safe(lambda: _get("/permissions"))

    @mcp.tool(name="get_blog_capabilities")
    async def get_blog_capabilities() -> dict[str, Any]:
        """Return supported CMS features."""
        return await safe(lambda: _get("/capabilities"))


async def _get(path: str) -> dict[str, Any]:
    async with BlogApiClient() as client:
        return await client.get(path)
