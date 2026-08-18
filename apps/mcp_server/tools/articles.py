from typing import Any

from mcp.server import MCPServer

from apps.mcp_server.client import BlogApiClient
from apps.mcp_server.tools.common import safe


async def request(
    method: str,
    path: str,
    *,
    json: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    async with BlogApiClient() as client:
        return await client.request(method, path, json=json, params=params)


def register(mcp: MCPServer) -> None:
    @mcp.tool(name="list_articles")
    async def list_articles(
        status: str | None = None,
        tag: str | None = None,
        category: str | None = None,
        include_deleted: bool = False,
        limit: int = 20,
        cursor: int = 0,
    ) -> dict[str, Any]:
        """List fictional articles with filters and pagination."""
        return await safe(
            lambda: request(
                "GET",
                "/articles",
                params={
                    "status": status,
                    "tag": tag,
                    "category": category,
                    "include_deleted": include_deleted,
                    "limit": limit,
                    "cursor": cursor,
                },
            )
        )

    @mcp.tool(name="search_articles")
    async def search_articles(query: str, limit: int = 20, cursor: int = 0) -> dict[str, Any]:
        """Search local article text."""
        return await safe(
            lambda: request(
                "GET", "/articles", params={"query": query, "limit": limit, "cursor": cursor}
            )
        )

    @mcp.tool(name="get_article")
    async def get_article(article_id: str) -> dict[str, Any]:
        """Read a fictional article by ID."""
        return await safe(lambda: request("GET", f"/articles/{article_id}"))

    @mcp.tool(name="get_article_by_slug")
    async def get_article_by_slug(slug: str) -> dict[str, Any]:
        """Read a fictional article by slug."""
        return await safe(lambda: request("GET", f"/articles/by-slug/{slug}"))

    @mcp.tool(name="get_article_metadata")
    async def get_article_metadata(article_id: str) -> dict[str, Any]:
        """Read compact article metadata."""
        result = await get_article(article_id)
        return {
            key: value
            for key, value in result.items()
            if key not in {"content_markdown", "content_html"}
        }

    @mcp.tool(name="get_article_preview")
    async def get_article_preview(article_id: str) -> dict[str, Any]:
        """Return rendered local preview metadata."""
        return await safe(lambda: request("GET", f"/articles/{article_id}/preview"))

    @mcp.tool(name="validate_article")
    async def validate_article(article_id: str) -> dict[str, Any]:
        """Validate publication rules without mutation."""
        return await safe(lambda: request("POST", f"/articles/{article_id}/validate"))

    @mcp.tool(name="create_article")
    async def create_article(
        title: str,
        content_markdown: str = "",
        slug: str | None = None,
        excerpt: str = "",
        seo_title: str | None = None,
        seo_description: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Create a DRAFT only; never publishes implicitly."""

        async def call() -> dict[str, Any]:
            async with BlogApiClient() as client:
                return await client.create_article(
                    {
                        "title": title,
                        "content_markdown": content_markdown,
                        "slug": slug,
                        "excerpt": excerpt,
                        "seo_title": seo_title,
                        "seo_description": seo_description,
                    },
                    idempotency_key,
                )

        return await safe(call)

    @mcp.tool(name="update_article")
    async def update_article(
        article_id: str,
        expected_version: int,
        title: str | None = None,
        slug: str | None = None,
        excerpt: str | None = None,
        content_markdown: str | None = None,
        seo_title: str | None = None,
        seo_description: str | None = None,
        change_summary: str | None = None,
    ) -> dict[str, Any]:
        """Update article fields with optimistic concurrency."""
        values = {
            key: value
            for key, value in locals().items()
            if key not in {"article_id"} and value is not None
        }
        return await safe(lambda: request("PATCH", f"/articles/{article_id}", json=values))

    @mcp.tool(name="patch_article")
    async def patch_article(
        article_id: str,
        expected_version: int,
        field: str,
        value: str,
        change_summary: str | None = None,
    ) -> dict[str, Any]:
        """Patch one allowed text field with optimistic concurrency."""
        allowed = {"title", "slug", "excerpt", "content_markdown", "seo_title", "seo_description"}
        if field not in allowed:
            return {
                "ok": False,
                "error": {
                    "code": "validation_error",
                    "message": "Unsupported patch field",
                    "details": {"allowed": sorted(allowed)},
                },
            }
        return await safe(
            lambda: request(
                "PATCH",
                f"/articles/{article_id}",
                json={
                    "expected_version": expected_version,
                    field: value,
                    "change_summary": change_summary,
                },
            )
        )

    async def mutate(
        article_id: str, expected_version: int, action: str, method: str = "POST"
    ) -> dict[str, Any]:
        return await safe(
            lambda: request(
                method,
                f"/articles/{article_id}/{action}" if action else f"/articles/{article_id}",
                json={"expected_version": expected_version},
            )
        )

    @mcp.tool(name="set_article_status")
    async def set_article_status(
        article_id: str, expected_version: int, status: str
    ) -> dict[str, Any]:
        """Move to draft, review, or archived; publishing is separate."""
        if status not in {"draft", "review", "archived"}:
            return {
                "ok": False,
                "error": {
                    "code": "validation_error",
                    "message": "Use publish_article or unpublish_article for publication changes",
                },
            }
        return await safe(
            lambda: request(
                "POST",
                f"/articles/{article_id}/status",
                json={"expected_version": expected_version, "status": status},
            )
        )

    @mcp.tool(name="publish_article")
    async def publish_article(article_id: str, expected_version: int) -> dict[str, Any]:
        """Validate and explicitly publish an article."""
        return await mutate(article_id, expected_version, "publish")

    @mcp.tool(name="unpublish_article")
    async def unpublish_article(article_id: str, expected_version: int) -> dict[str, Any]:
        """Explicitly remove an article from the public blog."""
        return await mutate(article_id, expected_version, "unpublish")

    @mcp.tool(name="archive_article")
    async def archive_article(article_id: str, expected_version: int) -> dict[str, Any]:
        """Archive an article without deleting it."""
        return await mutate(article_id, expected_version, "archive")

    @mcp.tool(name="soft_delete_article")
    async def soft_delete_article(
        article_id: str, expected_version: int, confirm: bool = False
    ) -> dict[str, Any]:
        """Soft delete only after explicit confirmation."""
        if not confirm:
            return {
                "ok": False,
                "error": {
                    "code": "confirmation_required",
                    "message": "Set confirm=true after reviewing impact",
                },
            }
        return await mutate(article_id, expected_version, "", "DELETE")

    @mcp.tool(name="restore_article")
    async def restore_article(article_id: str, expected_version: int) -> dict[str, Any]:
        """Restore a soft-deleted article."""
        return await mutate(article_id, expected_version, "restore")

    @mcp.tool(name="duplicate_article")
    async def duplicate_article(article_id: str) -> dict[str, Any]:
        """Duplicate an article as a new draft."""
        return await safe(lambda: request("POST", f"/articles/{article_id}/duplicate"))
