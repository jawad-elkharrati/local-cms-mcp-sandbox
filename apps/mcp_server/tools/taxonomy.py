from typing import Any

from mcp.server import MCPServer

from apps.mcp_server.tools.articles import request
from apps.mcp_server.tools.common import safe


def register(mcp: MCPServer) -> None:
    @mcp.tool(name="list_tags")
    async def list_tags(query: str | None = None) -> dict[str, Any]:
        """List/search the tag catalog."""
        return await safe(lambda: request("GET", "/tags", params={"query": query}))

    @mcp.tool(name="create_tag")
    async def create_tag(name: str, description: str = "") -> dict[str, Any]:
        """Create a local tag."""
        return await safe(
            lambda: request("POST", "/tags", json={"name": name, "description": description})
        )

    @mcp.tool(name="update_tag")
    async def update_tag(tag_id: int, name: str, description: str = "") -> dict[str, Any]:
        """Update a tag."""
        return await safe(
            lambda: request(
                "PATCH", f"/tags/{tag_id}", json={"name": name, "description": description}
            )
        )

    @mcp.tool(name="delete_tag")
    async def delete_tag(tag_id: int, confirm: bool = False) -> dict[str, Any]:
        """Delete an unused tag after confirmation."""
        if not confirm:
            return {
                "ok": False,
                "error": {"code": "confirmation_required", "message": "Set confirm=true"},
            }
        return await safe(lambda: request("DELETE", f"/tags/{tag_id}"))

    @mcp.tool(name="list_categories")
    async def list_categories() -> dict[str, Any]:
        """List the category hierarchy."""
        return await safe(lambda: request("GET", "/categories"))

    @mcp.tool(name="create_category")
    async def create_category(
        name: str, description: str = "", parent_id: int | None = None
    ) -> dict[str, Any]:
        """Create a local category."""
        return await safe(
            lambda: request(
                "POST",
                "/categories",
                json={"name": name, "description": description, "parent_id": parent_id},
            )
        )

    @mcp.tool(name="update_category")
    async def update_category(
        category_id: int, name: str, description: str = "", parent_id: int | None = None
    ) -> dict[str, Any]:
        """Update a category."""
        return await safe(
            lambda: request(
                "PATCH",
                f"/categories/{category_id}",
                json={"name": name, "description": description, "parent_id": parent_id},
            )
        )

    @mcp.tool(name="delete_category")
    async def delete_category(category_id: int, confirm: bool = False) -> dict[str, Any]:
        """Delete a safe category after confirmation."""
        if not confirm:
            return {
                "ok": False,
                "error": {"code": "confirmation_required", "message": "Set confirm=true"},
            }
        return await safe(lambda: request("DELETE", f"/categories/{category_id}"))

    @mcp.tool(name="replace_article_taxonomy")
    async def replace_article_taxonomy(
        article_id: str, expected_version: int, tag_ids: list[int], category_ids: list[int]
    ) -> dict[str, Any]:
        """Replace an article's tag/category assignments."""
        return await safe(
            lambda: request(
                "PUT",
                f"/articles/{article_id}/taxonomy",
                json={
                    "expected_version": expected_version,
                    "tag_ids": tag_ids,
                    "category_ids": category_ids,
                },
            )
        )
