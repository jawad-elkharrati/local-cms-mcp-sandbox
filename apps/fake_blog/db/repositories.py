from typing import cast

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Article


class ArticleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, article_id: str, *, include_deleted: bool = False) -> Article | None:
        statement: Select[tuple[Article]] = select(Article).where(Article.id == article_id)
        if not include_deleted:
            statement = statement.where(Article.deleted_at.is_(None))
        return cast(Article | None, await self.session.scalar(statement))

    async def by_slug(self, slug: str) -> Article | None:
        return cast(
            Article | None,
            await self.session.scalar(
                select(Article).where(Article.slug == slug, Article.deleted_at.is_(None))
            ),
        )

    async def add(self, article: Article) -> Article:
        self.session.add(article)
        await self.session.flush()
        return article
