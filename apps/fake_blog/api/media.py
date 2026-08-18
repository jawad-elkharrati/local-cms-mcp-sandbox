import hashlib
import re
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.fake_blog.auth import Actor, require_scope
from apps.fake_blog.db.models import Article, AuditLog, MediaAsset
from apps.fake_blog.db.session import get_session
from apps.fake_blog.domain.storage import ObjectStorage
from apps.fake_blog.errors import ApiError
from apps.fake_blog.settings import get_settings

router = APIRouter(tags=["media"])
Session = Annotated[AsyncSession, Depends(get_session)]
ALLOWED = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/webp": (b"RIFF",),
    "application/pdf": (b"%PDF",),
}


class MediaPatch(BaseModel):
    alt_text: str | None = Field(default=None, max_length=500)
    caption: str | None = Field(default=None, max_length=1000)


class FeaturedMedia(BaseModel):
    media_id: str | None
    expected_version: int


def media_data(item: MediaAsset) -> dict[str, object]:
    return {
        "id": item.id,
        "filename": item.filename,
        "mime_type": item.mime_type,
        "size_bytes": item.size_bytes,
        "width": item.width,
        "height": item.height,
        "alt_text": item.alt_text,
        "caption": item.caption,
        "sha256": item.sha256,
        "deleted_at": item.deleted_at,
        "url": f"/api/v1/media/{item.id}/content",
    }


@router.get("/media")
async def list_media(session: Session, _: Actor = require_scope("media:read")) -> dict[str, object]:
    rows = (
        await session.scalars(
            select(MediaAsset)
            .where(MediaAsset.deleted_at.is_(None))
            .order_by(MediaAsset.created_at.desc())
        )
    ).all()
    return {"items": [media_data(item) for item in rows]}


@router.post("/media", status_code=201)
async def upload_media(
    request: Request,
    session: Session,
    actor: Actor = require_scope("media:upload"),
    file: UploadFile = File(),
    alt_text: str | None = Form(default=None),
    caption: str | None = Form(default=None),
) -> dict[str, object]:
    mime = file.content_type or "application/octet-stream"
    if mime not in ALLOWED:
        raise ApiError(415, "invalid_media_type", "Executable or unsupported media type")
    data = await file.read(get_settings().max_upload_bytes + 1)
    if len(data) > get_settings().max_upload_bytes:
        raise ApiError(413, "upload_too_large", "Upload exceeds local size limit")
    if not any(data.startswith(signature) for signature in ALLOWED[mime]):
        raise ApiError(415, "invalid_media_signature", "File signature does not match MIME type")
    source_name = Path((file.filename or "upload").replace("\\", "/")).name
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", source_name).lstrip(".") or "upload"
    item = MediaAsset(
        object_key=f"uploads/{uuid.uuid4()}",
        filename=safe_name,
        mime_type=mime,
        size_bytes=len(data),
        width=None,
        height=None,
        alt_text=alt_text,
        caption=caption,
        sha256=hashlib.sha256(data).hexdigest(),
        uploaded_by=actor.id,
    )
    session.add(item)
    await session.flush()
    await ObjectStorage().put(item.object_key, data, mime)
    session.add(
        AuditLog(
            request_id=request.state.request_id,
            actor_id=actor.id,
            action="media.upload",
            entity_type="media",
            entity_id=item.id,
            before_json=None,
            after_json=media_data(item),
            metadata_json={"stored_locally": True},
        )
    )
    return media_data(item)


@router.get("/media/{media_id}/content")
async def media_content(
    media_id: str, session: Session, _: Actor = require_scope("media:read")
) -> Response:
    item = await session.get(MediaAsset, media_id)
    if not item or item.deleted_at:
        raise ApiError(404, "not_found", "Media not found")
    try:
        content = await ObjectStorage().get(item.object_key)
    except (KeyError, OSError) as exc:
        raise ApiError(503, "dependency_unavailable", "Media object is unavailable") from exc
    return Response(content, media_type=item.mime_type)


@router.get("/media/{media_id}")
async def get_media(
    media_id: str, session: Session, _: Actor = require_scope("media:read")
) -> dict[str, object]:
    item = await session.get(MediaAsset, media_id)
    if not item or item.deleted_at:
        raise ApiError(404, "not_found", "Media not found")
    return media_data(item)


@router.patch("/media/{media_id}")
async def patch_media(
    media_id: str, payload: MediaPatch, session: Session, _: Actor = require_scope("media:upload")
) -> dict[str, object]:
    item = await session.get(MediaAsset, media_id)
    if not item:
        raise ApiError(404, "not_found", "Media not found")
    if "alt_text" in payload.model_fields_set:
        item.alt_text = payload.alt_text
    if "caption" in payload.model_fields_set:
        item.caption = payload.caption
    return media_data(item)


@router.get("/media/{media_id}/usage")
async def media_usage(
    media_id: str, session: Session, _: Actor = require_scope("media:read")
) -> dict[str, object]:
    rows = (
        await session.scalars(
            select(Article).where(
                Article.featured_media_id == media_id, Article.deleted_at.is_(None)
            )
        )
    ).all()
    return {"items": [{"id": item.id, "title": item.title, "status": item.status} for item in rows]}


@router.delete("/media/{media_id}")
async def delete_media(
    media_id: str, session: Session, _: Actor = require_scope("media:delete")
) -> dict[str, object]:
    item = await session.get(MediaAsset, media_id)
    if not item:
        raise ApiError(404, "not_found", "Media not found")
    usage = await session.scalar(
        select(func.count())
        .select_from(Article)
        .where(Article.featured_media_id == media_id, Article.deleted_at.is_(None))
    )
    if usage:
        raise ApiError(409, "conflict", "Media is used as a featured image", {"usage_count": usage})
    from datetime import UTC, datetime

    item.deleted_at = datetime.now(UTC)
    return media_data(item)


@router.put("/articles/{article_id}/featured-media")
async def featured_media(
    article_id: str,
    payload: FeaturedMedia,
    request: Request,
    session: Session,
    actor: Actor = require_scope("article:update"),
) -> dict[str, object]:
    from apps.fake_blog.domain.articles import ArticleService
    from apps.fake_blog.schemas.articles import article_dict

    svc = ArticleService(session, actor, request.state.request_id)
    article = await svc.get(article_id)
    svc._version(article, payload.expected_version)
    if payload.media_id and not await session.get(MediaAsset, payload.media_id):
        raise ApiError(404, "not_found", "Media not found")
    before = article.snapshot()
    article.featured_media_id = payload.media_id
    article.version += 1
    await svc._record(article, "article.featured_media.set", before, "Set featured media")
    return article_dict(article)
