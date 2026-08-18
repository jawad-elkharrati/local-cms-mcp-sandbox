from apps.fake_blog.db.models import Article


def test_article_snapshot_is_stable() -> None:
    article = Article(id="a", title="Local Article", slug="local-article", author_id="u")
    article.version = 1
    article.status = "draft"
    article.excerpt = ""
    article.content_markdown = ""
    article.content_html = ""
    snapshot = article.snapshot()
    assert snapshot["id"] == "a"
    assert snapshot["status"] == "draft"
    assert snapshot["version"] == 1
