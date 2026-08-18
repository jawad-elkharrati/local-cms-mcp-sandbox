from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.fake_blog.auth import Actor, require_scope
from apps.fake_blog.db.models import Article, ArticleRevision, AuditLog, Category, Tag
from apps.fake_blog.db.session import get_session
from apps.fake_blog.domain.articles import ArticleService, revision_diff
from apps.fake_blog.errors import ApiError
from apps.fake_blog.schemas.articles import (
    ArticleCreate,
    ArticlePatch,
    StatusRequest,
    TaxonomyReplace,
    VersionRequest,
    article_dict,
)

router = APIRouter(prefix="/articles", tags=["articles"])
Session = Annotated[AsyncSession, Depends(get_session)]


def service(session: AsyncSession, actor: Actor, request: Request) -> ArticleService:
    return ArticleService(session, actor, request.state.request_id)


@router.get("")
async def list_articles(
    session: Session,
    actor: Actor = require_scope("article:read"),
    status_filter: str | None = Query(default=None, alias="status"),
    query: str | None = None,
    include_deleted: bool = False,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: int = Query(default=0, ge=0),
) -> dict[str, object]:
    statement = select(Article)
    if not include_deleted or not actor.has("article:restore"):
        statement = statement.where(Article.deleted_at.is_(None))
    if status_filter:
        statement = statement.where(Article.status == status_filter)
    if query:
        pattern = f"%{query}%"
        statement = statement.where(
            or_(
                Article.title.ilike(pattern),
                Article.slug.ilike(pattern),
                Article.excerpt.ilike(pattern),
                Article.content_markdown.ilike(pattern),
            )
        )
    rows = list(
        (
            await session.scalars(
                statement.order_by(Article.updated_at.desc()).offset(cursor).limit(limit + 1)
            )
        ).all()
    )
    return {
        "items": [article_dict(item) for item in rows[:limit]],
        "next_cursor": cursor + limit if len(rows) > limit else None,
        "limit": limit,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_article(
    payload: ArticleCreate,
    request: Request,
    response: Response,
    session: Session,
    actor: Actor = require_scope("article:create"),
    idempotency_key: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    article = await service(session, actor, request).create(payload, idempotency_key)
    response.headers["ETag"] = f'W/"{article.version}"'
    return article_dict(article)


@router.get("/by-slug/{slug}")
async def by_slug(
    slug: str, session: Session, actor: Actor = require_scope("article:read")
) -> dict[str, object]:
    article = await session.scalar(
        select(Article).where(Article.slug == slug, Article.deleted_at.is_(None))
    )
    if not article:
        raise ApiError(404, "not_found", "Article not found")
    return article_dict(article)


@router.get("/{article_id}")
async def get_article(
    article_id: str,
    request: Request,
    session: Session,
    actor: Actor = require_scope("article:read"),
) -> dict[str, object]:
    return article_dict(
        await service(session, actor, request).get(
            article_id, include_deleted=actor.has("article:restore")
        )
    )


@router.patch("/{article_id}")
async def patch_article(
    article_id: str,
    payload: ArticlePatch,
    request: Request,
    session: Session,
    actor: Actor = require_scope("article:update"),
) -> dict[str, object]:
    return article_dict(await service(session, actor, request).patch(article_id, payload))


@router.post("/{article_id}/validate")
async def validate_article(
    article_id: str,
    request: Request,
    session: Session,
    actor: Actor = require_scope("article:read"),
) -> dict[str, Any]:
    svc = service(session, actor, request)
    return svc.validate(await svc.get(article_id))


async def transition(
    article_id: str,
    payload: VersionRequest,
    action: str,
    request: Request,
    session: AsyncSession,
    actor: Actor,
) -> dict[str, object]:
    return article_dict(
        await service(session, actor, request).transition(
            article_id, payload.expected_version, action
        )
    )


@router.post("/{article_id}/publish")
async def publish(
    article_id: str,
    payload: VersionRequest,
    request: Request,
    session: Session,
    actor: Actor = require_scope("article:publish"),
) -> dict[str, object]:
    return await transition(article_id, payload, "publish", request, session, actor)


@router.post("/{article_id}/unpublish")
async def unpublish(
    article_id: str,
    payload: VersionRequest,
    request: Request,
    session: Session,
    actor: Actor = require_scope("article:unpublish"),
) -> dict[str, object]:
    return await transition(article_id, payload, "unpublish", request, session, actor)


@router.post("/{article_id}/archive")
async def archive(
    article_id: str,
    payload: VersionRequest,
    request: Request,
    session: Session,
    actor: Actor = require_scope("article:update"),
) -> dict[str, object]:
    return await transition(article_id, payload, "archive", request, session, actor)


@router.post("/{article_id}/status")
async def set_status(
    article_id: str,
    payload: StatusRequest,
    request: Request,
    session: Session,
    actor: Actor = require_scope("article:update"),
) -> dict[str, object]:
    if payload.status not in {"draft", "review", "archived"}:
        raise ApiError(400, "validation_error", "Use the dedicated publish/unpublish tools")
    action = "archive" if payload.status == "archived" else payload.status
    return await transition(article_id, payload, action, request, session, actor)


@router.delete("/{article_id}")
async def soft_delete(
    article_id: str,
    payload: VersionRequest,
    request: Request,
    session: Session,
    actor: Actor = require_scope("article:delete"),
) -> dict[str, object]:
    return await transition(article_id, payload, "delete", request, session, actor)


@router.post("/{article_id}/restore")
async def restore(
    article_id: str,
    payload: VersionRequest,
    request: Request,
    session: Session,
    actor: Actor = require_scope("article:restore"),
) -> dict[str, object]:
    return await transition(article_id, payload, "restore", request, session, actor)


@router.post("/{article_id}/duplicate", status_code=201)
async def duplicate(
    article_id: str,
    request: Request,
    session: Session,
    actor: Actor = require_scope("article:create"),
) -> dict[str, object]:
    svc = service(session, actor, request)
    source = await svc.get(article_id)
    payload = ArticleCreate(
        title=f"Copy of {source.title}",
        slug=f"{source.slug}-copy",
        excerpt=source.excerpt,
        content_markdown=source.content_markdown,
        seo_title=source.seo_title,
        seo_description=source.seo_description,
    )
    return article_dict(await svc.create(payload, None))


@router.get("/{article_id}/preview")
async def preview(
    article_id: str,
    request: Request,
    session: Session,
    actor: Actor = require_scope("article:read"),
) -> dict[str, object]:
    article = await service(session, actor, request).get(article_id)
    return {
        "article_id": article.id,
        "version": article.version,
        "rendered_html": article.content_html,
        "preview_url": f"/preview/{article.id}",
    }


@router.get("/{article_id}/revisions")
async def revisions(
    article_id: str, session: Session, actor: Actor = require_scope("article:read")
) -> dict[str, object]:
    rows = list(
        (
            await session.scalars(
                select(ArticleRevision)
                .where(ArticleRevision.article_id == article_id)
                .order_by(ArticleRevision.version.desc())
            )
        ).all()
    )
    return {
        "items": [
            {
                "id": row.id,
                "version": row.version,
                "change_summary": row.change_summary,
                "created_at": row.created_at,
            }
            for row in rows
        ]
    }


@router.get("/{article_id}/revisions/{version}")
async def revision(
    article_id: str, version: int, session: Session, actor: Actor = require_scope("article:read")
) -> dict[str, object]:
    row = await session.scalar(
        select(ArticleRevision).where(
            ArticleRevision.article_id == article_id, ArticleRevision.version == version
        )
    )
    if not row:
        raise ApiError(404, "not_found", "Revision not found")
    return {
        "version": row.version,
        "snapshot": row.snapshot_json,
        "change_summary": row.change_summary,
    }


@router.get("/{article_id}/revisions/{a}/diff/{b}")
async def diff(
    article_id: str, a: int, b: int, session: Session, actor: Actor = require_scope("article:read")
) -> dict[str, object]:
    rows = list(
        (
            await session.scalars(
                select(ArticleRevision).where(
                    ArticleRevision.article_id == article_id, ArticleRevision.version.in_([a, b])
                )
            )
        ).all()
    )
    by_version = {row.version: row for row in rows}
    if a not in by_version or b not in by_version:
        raise ApiError(404, "not_found", "Revision not found")
    return revision_diff(by_version[a], by_version[b])


@router.post("/{article_id}/revisions/{version}/restore")
async def restore_revision(
    article_id: str,
    version: int,
    payload: VersionRequest,
    request: Request,
    session: Session,
    actor: Actor = require_scope("article:restore"),
) -> dict[str, object]:
    return article_dict(
        await service(session, actor, request).restore_revision(
            article_id, version, payload.expected_version
        )
    )


@router.put("/{article_id}/taxonomy")
async def replace_taxonomy(
    article_id: str,
    payload: TaxonomyReplace,
    request: Request,
    session: Session,
    actor: Actor = require_scope("taxonomy:assign"),
) -> dict[str, object]:
    svc = service(session, actor, request)
    article = await svc.get(article_id)
    svc._version(article, payload.expected_version)
    before = article.snapshot()
    article.tags = (
        list((await session.scalars(select(Tag).where(Tag.id.in_(payload.tag_ids)))).all())
        if payload.tag_ids
        else []
    )
    article.categories = (
        list(
            (
                await session.scalars(select(Category).where(Category.id.in_(payload.category_ids)))
            ).all()
        )
        if payload.category_ids
        else []
    )
    article.version += 1
    await svc._record(article, "article.taxonomy.replace", before, "Replaced taxonomy")
    return article_dict(article)


@router.get("/{article_id}/audit")
async def article_audit(
    article_id: str, session: Session, actor: Actor = require_scope("audit:read")
) -> dict[str, object]:
    rows = list(
        (
            await session.scalars(
                select(AuditLog)
                .where(AuditLog.entity_type == "article", AuditLog.entity_id == article_id)
                .order_by(AuditLog.created_at.desc())
            )
        ).all()
    )
    return {
        "items": [
            {
                "id": row.id,
                "request_id": row.request_id,
                "action": row.action,
                "created_at": row.created_at,
                "before": row.before_json,
                "after": row.after_json,
            }
            for row in rows
        ]
    }
