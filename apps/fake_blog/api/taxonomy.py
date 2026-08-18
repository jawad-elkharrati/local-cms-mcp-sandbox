import re
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.fake_blog.auth import Actor, require_scope
from apps.fake_blog.db.models import Category, Tag, article_categories, article_tags
from apps.fake_blog.db.session import get_session
from apps.fake_blog.errors import ApiError

router = APIRouter(tags=["taxonomy"])
Session = Annotated[AsyncSession, Depends(get_session)]


class TaxonomyInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    parent_id: int | None = None


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def tag_data(item: Tag) -> dict[str, object]:
    return {"id": item.id, "name": item.name, "slug": item.slug, "description": item.description}


def category_data(item: Category) -> dict[str, object]:
    return {
        "id": item.id,
        "name": item.name,
        "slug": item.slug,
        "description": item.description,
        "parent_id": item.parent_id,
    }


@router.get("/tags")
async def list_tags(
    session: Session, _: Actor = require_scope("taxonomy:read"), query: str | None = None
) -> dict[str, object]:
    statement = select(Tag)
    if query:
        statement = statement.where(Tag.name.ilike(f"%{query}%"))
    return {
        "items": [
            tag_data(item) for item in (await session.scalars(statement.order_by(Tag.name))).all()
        ]
    }


@router.post("/tags", status_code=201)
async def create_tag(
    payload: TaxonomyInput, session: Session, _: Actor = require_scope("taxonomy:manage")
) -> dict[str, object]:
    item = Tag(name=payload.name, slug=slug(payload.name), description=payload.description)
    session.add(item)
    await session.flush()
    return tag_data(item)


@router.patch("/tags/{item_id}")
async def update_tag(
    item_id: int,
    payload: TaxonomyInput,
    session: Session,
    _: Actor = require_scope("taxonomy:manage"),
) -> dict[str, object]:
    item = await session.get(Tag, item_id)
    if not item:
        raise ApiError(404, "not_found", "Tag not found")
    item.name, item.slug, item.description = payload.name, slug(payload.name), payload.description
    return tag_data(item)


@router.delete("/tags/{item_id}", status_code=204)
async def delete_tag(
    item_id: int, session: Session, _: Actor = require_scope("taxonomy:manage")
) -> Response:
    usage = await session.scalar(
        select(func.count()).select_from(article_tags).where(article_tags.c.tag_id == item_id)
    )
    if usage:
        raise ApiError(409, "conflict", "Tag is assigned to articles", {"usage_count": usage})
    await session.execute(delete(Tag).where(Tag.id == item_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/categories")
async def list_categories(
    session: Session, _: Actor = require_scope("taxonomy:read")
) -> dict[str, object]:
    return {
        "items": [
            category_data(item)
            for item in (await session.scalars(select(Category).order_by(Category.name))).all()
        ]
    }


@router.post("/categories", status_code=201)
async def create_category(
    payload: TaxonomyInput, session: Session, _: Actor = require_scope("taxonomy:manage")
) -> dict[str, object]:
    item = Category(
        name=payload.name,
        slug=slug(payload.name),
        description=payload.description,
        parent_id=payload.parent_id,
    )
    session.add(item)
    await session.flush()
    return category_data(item)


@router.patch("/categories/{item_id}")
async def update_category(
    item_id: int,
    payload: TaxonomyInput,
    session: Session,
    _: Actor = require_scope("taxonomy:manage"),
) -> dict[str, object]:
    item = await session.get(Category, item_id)
    if not item:
        raise ApiError(404, "not_found", "Category not found")
    item.name, item.slug, item.description, item.parent_id = (
        payload.name,
        slug(payload.name),
        payload.description,
        payload.parent_id,
    )
    return category_data(item)


@router.delete("/categories/{item_id}", status_code=204)
async def delete_category(
    item_id: int, session: Session, _: Actor = require_scope("taxonomy:manage")
) -> Response:
    usage = await session.scalar(
        select(func.count())
        .select_from(article_categories)
        .where(article_categories.c.category_id == item_id)
    )
    if usage or await session.scalar(
        select(func.count()).select_from(Category).where(Category.parent_id == item_id)
    ):
        raise ApiError(409, "conflict", "Category is assigned or has children")
    await session.execute(delete(Category).where(Category.id == item_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
