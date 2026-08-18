import html
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.fake_blog.db.models import Article, ArticleRevision, AuditLog
from apps.fake_blog.db.session import get_session
from apps.fake_blog.errors import ApiError
from apps.fake_blog.settings import get_settings

router = APIRouter(include_in_schema=False)
Session = Annotated[AsyncSession, Depends(get_session)]


def page(title: str, body: str) -> HTMLResponse:
    css = "body{font:16px system-ui;max-width:900px;margin:2rem auto;padding:0 1rem;color:#18202a}nav{display:flex;gap:1rem}article{border-bottom:1px solid #ddd;padding:1rem 0}.badge{background:#e8eef7;padding:.2rem .5rem;border-radius:.4rem}pre{white-space:pre-wrap;background:#f5f7fa;padding:1rem}a{color:#1456a0}"
    return HTMLResponse(
        f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title><style>{css}</style></head><body><nav><a href='/'>Fake Blog</a><a href='/admin'>Admin diagnostics</a><a href='/docs'>API docs</a></nav><h1>{html.escape(title)}</h1>{body}</body></html>"
    )


@router.get("/", response_class=HTMLResponse)
async def index(session: Session) -> HTMLResponse:
    rows = (
        await session.scalars(
            select(Article)
            .where(Article.status == "published", Article.deleted_at.is_(None))
            .order_by(Article.published_at.desc())
        )
    ).all()
    body = "".join(
        f"<article><h2><a href='/articles/{html.escape(item.slug)}'>{html.escape(item.title)}</a></h2><p>{html.escape(item.excerpt)}</p><small>{item.published_at or ''}</small></article>"
        for item in rows
    )
    return page("Local Fictional Blog", body or "<p>No published articles.</p>")


@router.get("/articles/{slug}", response_class=HTMLResponse)
async def public_article(slug: str, session: Session) -> HTMLResponse:
    item = await session.scalar(
        select(Article).where(
            Article.slug == slug, Article.status == "published", Article.deleted_at.is_(None)
        )
    )
    if not item:
        raise ApiError(404, "not_found", "Published article not found")
    return page(
        item.title, f"<p>{html.escape(item.excerpt)}</p><article>{item.content_html}</article>"
    )


@router.get("/preview/{article_id}", response_class=HTMLResponse)
async def preview(
    article_id: str, session: Session, token: str = Query(default="")
) -> HTMLResponse:
    if get_settings().app_env != "local" or token != get_settings().preview_token:
        raise ApiError(403, "forbidden", "Valid local preview token required")
    item = await session.get(Article, article_id)
    if not item:
        raise ApiError(404, "not_found", "Article not found")
    return page(
        f"Preview: {item.title}",
        f"<p><span class='badge'>{item.status}</span> version {item.version}</p><article>{item.content_html}</article>",
    )


@router.get("/admin", response_class=HTMLResponse)
async def admin(session: Session) -> HTMLResponse:
    count_rows = (
        await session.execute(
            select(Article.status, func.count())
            .where(Article.deleted_at.is_(None))
            .group_by(Article.status)
        )
    ).all()
    counts: dict[str, int] = {name: count for name, count in count_rows}
    audits = (
        await session.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(10))
    ).all()
    body = (
        "<h2>Article counts</h2><ul>"
        + "".join(f"<li>{html.escape(key)}: {value}</li>" for key, value in sorted(counts.items()))
        + "</ul><h2>Latest audit events</h2><ul>"
        + "".join(
            f"<li>{html.escape(row.action)} - <code>{html.escape(row.request_id)}</code></li>"
            for row in audits
        )
        + "</ul>"
    )
    return page("Local Admin Diagnostics", body)


@router.get("/admin/articles/{article_id}", response_class=HTMLResponse)
async def admin_article(article_id: str, session: Session) -> HTMLResponse:
    item = await session.get(Article, article_id)
    if not item:
        raise ApiError(404, "not_found", "Article not found")
    revisions = (
        await session.scalars(
            select(ArticleRevision)
            .where(ArticleRevision.article_id == article_id)
            .order_by(ArticleRevision.version.desc())
        )
    ).all()
    timeline = "".join(
        f"<li>v{row.version}: {html.escape(row.change_summary or '')}</li>" for row in revisions
    )
    return page(
        f"Diagnostic: {item.title}",
        f"<p>Status <span class='badge'>{item.status}</span>; version {item.version}</p><h2>Revisions</h2><ul>{timeline}</ul><h2>Markdown</h2><pre>{html.escape(item.content_markdown)}</pre>",
    )
