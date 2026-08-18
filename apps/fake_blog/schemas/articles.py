from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ArticleCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=200)
    excerpt: str = Field(default="", max_length=500)
    content_markdown: str = ""
    seo_title: str | None = Field(default=None, max_length=200)
    seo_description: str | None = Field(default=None, max_length=500)


class ArticlePatch(BaseModel):
    expected_version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=200)
    excerpt: str | None = Field(default=None, max_length=500)
    content_markdown: str | None = None
    seo_title: str | None = Field(default=None, max_length=200)
    seo_description: str | None = Field(default=None, max_length=500)
    change_summary: str | None = Field(default=None, max_length=500)


class VersionRequest(BaseModel):
    expected_version: int = Field(ge=1)


class StatusRequest(VersionRequest):
    status: str


class TaxonomyReplace(BaseModel):
    tag_ids: list[int] = Field(default_factory=list, max_length=50)
    category_ids: list[int] = Field(default_factory=list, max_length=20)
    expected_version: int = Field(ge=1)


class ArticleResponse(BaseModel):
    id: str
    title: str
    slug: str
    excerpt: str
    content_markdown: str
    content_html: str
    status: str
    version: int
    featured_media_id: str | None
    seo_title: str | None
    seo_description: str | None
    published_at: datetime | None
    deleted_at: datetime | None
    tags: list[dict[str, object]]
    categories: list[dict[str, object]]

    @field_validator("published_at", "deleted_at", mode="before")
    @classmethod
    def accept_iso(cls, value: object) -> object:
        return value


def article_dict(article: object) -> dict[str, object]:
    tags = getattr(article, "tags", [])
    categories = getattr(article, "categories", [])
    return {
        "id": getattr(article, "id"),
        "title": getattr(article, "title"),
        "slug": getattr(article, "slug"),
        "excerpt": getattr(article, "excerpt"),
        "content_markdown": getattr(article, "content_markdown"),
        "content_html": getattr(article, "content_html"),
        "status": getattr(article, "status"),
        "version": getattr(article, "version"),
        "featured_media_id": getattr(article, "featured_media_id"),
        "seo_title": getattr(article, "seo_title"),
        "seo_description": getattr(article, "seo_description"),
        "published_at": getattr(article, "published_at"),
        "deleted_at": getattr(article, "deleted_at"),
        "tags": [{"id": item.id, "name": item.name, "slug": item.slug} for item in tags],
        "categories": [
            {"id": item.id, "name": item.name, "slug": item.slug} for item in categories
        ],
    }
