import difflib
from typing import Any

from mcp.server import MCPServer

from apps.mcp_server.tools.articles import request
from apps.mcp_server.tools.common import safe


def register(mcp: MCPServer) -> None:
    @mcp.tool(name="preview_article_change")
    async def preview_article_change(
        article_id: str, proposed_changes: dict[str, Any]
    ) -> dict[str, Any]:
        """Compute a diff without applying a mutation."""
        current = await request("GET", f"/articles/{article_id}")
        fields = {
            key: {"before": current.get(key), "after": value}
            for key, value in proposed_changes.items()
            if current.get(key) != value
        }
        content_diff = ""
        if "content_markdown" in proposed_changes:
            content_diff = "\n".join(
                difflib.unified_diff(
                    str(current.get("content_markdown", "")).splitlines(),
                    str(proposed_changes["content_markdown"]).splitlines(),
                    fromfile="current",
                    tofile="proposed",
                )
            )
        return {
            "dry_run": True,
            "article_id": article_id,
            "current_version": current["version"],
            "changed_fields": fields,
            "content_diff": content_diff,
        }

    @mcp.tool(name="dry_run_article_mutation")
    async def dry_run_article_mutation(
        article_id: str,
        expected_version: int,
        action: str,
        proposed_changes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Validate version, permissions, and publishing rules without commit."""

        async def call() -> dict[str, Any]:
            current = await request("GET", f"/articles/{article_id}")
            permissions = await request("GET", "/permissions")
            required = {
                "publish": "article:publish",
                "delete": "article:delete",
                "update": "article:update",
            }.get(action, "article:update")
            scopes = permissions.get("scopes", [])
            allowed = "*" in scopes or required in scopes
            return {
                "dry_run": True,
                "would_commit": False,
                "article_id": article_id,
                "version_matches": current["version"] == expected_version,
                "current_version": current["version"],
                "required_scope": required,
                "permission_allowed": allowed,
                "proposed_changes": proposed_changes or {},
            }

        return await safe(call)
