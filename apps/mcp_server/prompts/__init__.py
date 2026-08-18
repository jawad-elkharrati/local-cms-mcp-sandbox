from mcp.server import MCPServer


def register_prompts(mcp: MCPServer) -> None:
    @mcp.prompt(name="draft_article_workflow")
    def draft_article_workflow(topic: str, audience: str, desired_tags: str = "") -> str:
        return f"Draft safely for {audience} about {topic}. Search the corpus, run overlap checks, recommend existing tags ({desired_tags}), write original content, validate it, and call create_article only. The result must remain DRAFT."

    @mcp.prompt(name="edit_article_safely")
    def edit_article_safely(article_id: str, requested_change: str) -> str:
        return f"Read article {article_id}, note its version, preview this change: {requested_change}. Apply only with expected_version, then re-read and verify. If 409 occurs, stop and re-read."

    @mcp.prompt(name="prepare_article_for_publication")
    def prepare_article_for_publication(article_id: str) -> str:
        return f"For article {article_id}, validate publishing rules; run SEO, readability, taxonomy, media, duplicate, and link checks. Summarize blockers and request a separate explicit publish_article action. Do not publish inside this prompt."

    @mcp.prompt(name="investigate_content_overlap")
    def investigate_content_overlap(article_id_or_query: str) -> str:
        return f"Investigate {article_id_or_query} with similarity, duplicate, and cannibalization tools. Report engine, scores, thresholds, and evidence. Make no writes."

    @mcp.prompt(name="repair_failed_mcp_action")
    def repair_failed_mcp_action(request_id: str, error: str) -> str:
        return f"Diagnose local request {request_id}: {error}. Check MCP error code, token role/scopes, Fake Blog health, API request ID, and local dependencies. Never reveal or escalate the token."

    @mcp.prompt(name="editorial_audit")
    def editorial_audit(status: str = "draft,review", time_range: str = "all") -> str:
        return f"Review {status} articles for {time_range}. List concrete validation, SEO, readability, taxonomy, media, duplication, and link issues. Do not publish or mutate anything."
