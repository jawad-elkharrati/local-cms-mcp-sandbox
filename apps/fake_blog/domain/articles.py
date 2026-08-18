import difflib
import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any

import markdown
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.fake_blog.auth import Actor
from apps.fake_blog.db.models import Article, ArticleRevision, AuditLog, IdempotencyRecord
from apps.fake_blog.errors import ApiError
from apps.fake_blog.schemas.articles import ArticleCreate, ArticlePatch


def slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value[:200] or "untitled"


class ArticleService:
    def __init__(self, session: AsyncSession, actor: Actor, request_id: str) -> None:
        self.session = session
        self.actor = actor
        self.request_id = request_id

    async def get(self, article_id: str, *, include_deleted: bool = False) -> Article:
        statement = select(Article).where(Article.id == article_id)
        if not include_deleted:
            statement = statement.where(Article.deleted_at.is_(None))
        article = await self.session.scalar(statement)
        if article is None:
            raise ApiError(404, "not_found", "Article not found", {"article_id": article_id})
        return article

    async def create(self, payload: ArticleCreate, idempotency_key: str | None) -> Article:
        request_hash = hashlib.sha256(payload.model_dump_json().encode()).hexdigest()
        if idempotency_key:
            record = await self.session.scalar(
                select(IdempotencyRecord).where(
                    IdempotencyRecord.key == idempotency_key,
                    IdempotencyRecord.actor_id == self.actor.id,
                    IdempotencyRecord.route == "/articles",
                )
            )
            if record:
                if record.request_hash != request_hash:
                    raise ApiError(409, "idempotency_conflict", "Key was used with another payload")
                return await self.get(str(record.response_json["id"]))
        slug = slugify(payload.slug or payload.title)
        if await self.session.scalar(select(Article.id).where(Article.slug == slug)):
            raise ApiError(409, "duplicate_slug", "Article slug already exists", {"slug": slug})
        article = Article(
            title=payload.title,
            slug=slug,
            excerpt=payload.excerpt,
            content_markdown=payload.content_markdown,
            content_html=markdown.markdown(payload.content_markdown),
            status="draft",
            version=1,
            author_id=self.actor.id,
            seo_title=payload.seo_title,
            seo_description=payload.seo_description,
            canonical_path=f"/articles/{slug}",
        )
        article.tags = []
        article.categories = []
        self.session.add(article)
        await self.session.flush()
        await self._record(article, "article.create", None, "Created draft")
        if idempotency_key:
            self.session.add(
                IdempotencyRecord(
                    key=idempotency_key,
                    actor_id=self.actor.id,
                    route="/articles",
                    request_hash=request_hash,
                    response_status=201,
                    response_json={"id": article.id},
                    expires_at=datetime.now(UTC) + timedelta(days=1),
                )
            )
        return article

    async def patch(self, article_id: str, payload: ArticlePatch) -> Article:
        article = await self.get(article_id, include_deleted=True)
        self._version(article, payload.expected_version)
        if article.deleted_at:
            raise ApiError(400, "validation_error", "Deleted article cannot be edited")
        before = article.snapshot()
        values = payload.model_dump(
            exclude_unset=True, exclude={"expected_version", "change_summary"}
        )
        if "slug" in values and values["slug"] is not None:
            values["slug"] = slugify(str(values["slug"]))
            conflict = await self.session.scalar(
                select(Article.id).where(Article.slug == values["slug"], Article.id != article.id)
            )
            if conflict:
                raise ApiError(409, "duplicate_slug", "Article slug already exists")
        for key, value in values.items():
            setattr(article, key, value)
        if payload.content_markdown is not None:
            article.content_html = markdown.markdown(payload.content_markdown)
        article.version += 1
        article.updated_at = datetime.now(UTC)
        await self.session.flush()
        await self._record(article, "article.update", before, payload.change_summary)
        return article

    def validate(self, article: Article) -> dict[str, Any]:
        words = len(re.findall(r"\b\w+\b", article.content_markdown))
        errors: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []
        if not 10 <= len(article.title) <= 80:
            errors.append({"field": "title", "message": "Title must contain 10..80 characters"})
        if words < 150:
            errors.append({"field": "content_markdown", "message": "Publish requires 150 words"})
        if not article.seo_description or not 70 <= len(article.seo_description) <= 160:
            warnings.append(
                {"field": "seo_description", "message": "Recommended length is 70..160"}
            )
        if not article.tags and not article.categories:
            warnings.append(
                {"field": "taxonomy", "message": "At least one tag/category is recommended"}
            )
        return {"valid": not errors, "word_count": words, "errors": errors, "warnings": warnings}

    async def transition(self, article_id: str, expected: int, action: str) -> Article:
        article = await self.get(article_id, include_deleted=True)
        self._version(article, expected)
        before = article.snapshot()
        if action == "publish":
            if article.deleted_at:
                raise ApiError(400, "validation_error", "Deleted article cannot be published")
            report = self.validate(article)
            if not report["valid"]:
                raise ApiError(400, "validation_error", "Article is not publishable", report)
            article.status = "published"
            article.published_at = article.published_at or datetime.now(UTC)
        elif action == "unpublish":
            article.status = "draft"
            article.published_at = None
        elif action == "archive":
            article.status = "archived"
        elif action == "delete":
            article.previous_status = article.status
            article.deleted_at = datetime.now(UTC)
        elif action == "restore":
            article.deleted_at = None
            article.status = article.previous_status or "draft"
        else:
            article.status = action
        article.version += 1
        await self.session.flush()
        await self._record(article, f"article.{action}", before, action.title())
        return article

    async def restore_revision(self, article_id: str, version: int, expected: int) -> Article:
        article = await self.get(article_id, include_deleted=True)
        self._version(article, expected)
        revision = await self.session.scalar(
            select(ArticleRevision).where(
                ArticleRevision.article_id == article_id, ArticleRevision.version == version
            )
        )
        if revision is None:
            raise ApiError(404, "not_found", "Revision not found")
        before = article.snapshot()
        for field in [
            "title",
            "slug",
            "excerpt",
            "content_markdown",
            "content_html",
            "seo_title",
            "seo_description",
        ]:
            if field in revision.snapshot_json:
                setattr(article, field, revision.snapshot_json[field])
        article.version += 1
        await self.session.flush()
        await self._record(
            article, "article.revision.restore", before, f"Restored version {version}"
        )
        return article

    async def _record(
        self, article: Article, action: str, before: dict[str, Any] | None, summary: str | None
    ) -> None:
        after = article.snapshot()
        self.session.add(
            ArticleRevision(
                article_id=article.id,
                version=article.version,
                snapshot_json=after,
                change_summary=summary,
                actor_id=self.actor.id,
            )
        )
        self.session.add(
            AuditLog(
                request_id=self.request_id,
                actor_id=self.actor.id,
                action=action,
                entity_type="article",
                entity_id=article.id,
                before_json=before,
                after_json=after,
                metadata_json={},
            )
        )

    @staticmethod
    def _version(article: Article, expected: int) -> None:
        if article.version != expected:
            raise ApiError(
                409,
                "conflict",
                "Article version is stale; re-read before retrying",
                {"expected_version": expected, "current_version": article.version},
            )


def revision_diff(a: ArticleRevision, b: ArticleRevision) -> dict[str, Any]:
    fields = {}
    for key in sorted(set(a.snapshot_json) | set(b.snapshot_json)):
        if a.snapshot_json.get(key) != b.snapshot_json.get(key):
            fields[key] = {"before": a.snapshot_json.get(key), "after": b.snapshot_json.get(key)}
    content = "\n".join(
        difflib.unified_diff(
            str(a.snapshot_json.get("content_markdown", "")).splitlines(),
            str(b.snapshot_json.get("content_markdown", "")).splitlines(),
            fromfile=f"v{a.version}",
            tofile=f"v{b.version}",
        )
    )
    return {
        "from_version": a.version,
        "to_version": b.version,
        "changed_fields": fields,
        "content_diff": content,
    }


def mutation_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
