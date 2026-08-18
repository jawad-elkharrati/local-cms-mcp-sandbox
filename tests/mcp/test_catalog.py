import json

import httpx
import pytest
from mcp import Client

from apps.fake_blog.main import app
from apps.mcp_server import client as client_module
from apps.mcp_server import resources
from apps.mcp_server.server import mcp
from apps.mcp_server.settings import MCPSettings
from apps.mcp_server.tools import system

REQUIRED_CORE = {
    "whoami",
    "health_check",
    "get_service_info",
    "get_permissions",
    "get_blog_capabilities",
    "list_articles",
    "search_articles",
    "get_article",
    "get_article_by_slug",
    "get_article_metadata",
    "get_article_preview",
    "validate_article",
    "create_article",
    "update_article",
    "patch_article",
    "set_article_status",
    "publish_article",
    "unpublish_article",
    "archive_article",
    "soft_delete_article",
    "restore_article",
    "duplicate_article",
    "replace_article_taxonomy",
    "list_article_versions",
    "get_article_version",
    "diff_article_versions",
    "restore_article_version",
    "list_tags",
    "create_tag",
    "update_tag",
    "delete_tag",
    "list_categories",
    "create_category",
    "update_category",
    "delete_category",
    "list_media",
    "get_media",
    "upload_media",
    "update_media_metadata",
    "get_media_usage",
    "delete_media",
    "set_featured_media",
    "get_audit_log",
    "get_article_audit",
    "extract_keywords",
    "calculate_readability",
    "analyze_article_seo",
    "find_similar_articles",
    "detect_duplicate_content",
    "recommend_internal_links",
    "recommend_tags",
    "keyword_cannibalization_report",
    "content_gap_report",
    "semantic_search_articles",
    "preview_article_change",
    "dry_run_article_mutation",
}


class LocalBlogApiClient(client_module.BlogApiClient):
    def __init__(self) -> None:
        super().__init__(
            MCPSettings(
                _env_file=None,
                blog_api_base_url="http://localhost/api/v1",
                blog_api_token="dev-editor-token",
            ),
            transport=httpx.ASGITransport(app=app),
        )


@pytest.mark.anyio
async def test_catalog_names_and_static_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(system, "BlogApiClient", LocalBlogApiClient)
    monkeypatch.setattr(resources, "BlogApiClient", LocalBlogApiClient)
    async with Client(mcp) as client:
        tools = await client.list_tools()
        assert REQUIRED_CORE <= {item.name for item in tools.tools}
        prompts = await client.list_prompts()
        assert {item.name for item in prompts.prompts} == {
            "draft_article_workflow",
            "edit_article_safely",
            "prepare_article_for_publication",
            "investigate_content_overlap",
            "repair_failed_mcp_action",
            "editorial_audit",
        }
        resources_list = await client.list_resources()
        assert "cms://site/info" in {str(item.uri) for item in resources_list.resources}
        result = await client.call_tool("whoami", {})
        assert result.is_error is False
        assert result.structured_content["role"] == "editor"
        rules = await client.read_resource("cms://site/content-rules")
        assert json.loads(rules.contents[0].text)["publish_min_words"] == 150
        prompt = await client.get_prompt(
            "edit_article_safely",
            {"article_id": "fictional-id", "requested_change": "clarify intro"},
        )
        assert "expected_version" in prompt.messages[0].content.text
