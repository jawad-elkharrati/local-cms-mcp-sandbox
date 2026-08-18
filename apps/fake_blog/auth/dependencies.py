import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.fake_blog.db.models import ApiToken, User
from apps.fake_blog.db.session import get_session
from apps.fake_blog.errors import ApiError


@dataclass(frozen=True)
class Actor:
    id: str
    email: str
    display_name: str
    role: str
    scopes: frozenset[str]

    def has(self, scope: str) -> bool:
        return "*" in self.scopes or scope in self.scopes


async def get_actor(
    authorization: Annotated[str | None, Header()] = None,
    session: AsyncSession = Depends(get_session),
) -> Actor:
    if not authorization or not authorization.startswith("Bearer "):
        raise ApiError(401, "unauthorized", "A fake local Bearer token is required")
    raw = authorization.removeprefix("Bearer ").strip()
    token = await session.scalar(
        select(ApiToken).where(ApiToken.token_hash == hashlib.sha256(raw.encode()).hexdigest())
    )
    if token is None or token.revoked_at is not None:
        raise ApiError(401, "unauthorized", "The local token is invalid or revoked")
    expires = token.expires_at
    if expires is not None:
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if expires <= datetime.now(UTC):
            raise ApiError(401, "unauthorized", "The local token has expired")
    user = await session.get(User, token.user_id)
    if user is None or not user.active:
        raise ApiError(401, "unauthorized", "The local identity is inactive")
    token.last_used_at = datetime.now(UTC)
    return Actor(user.id, user.email, user.display_name, user.role, frozenset(token.scopes))


def require_scope(scope: str) -> Any:
    async def dependency(actor: Actor = Depends(get_actor)) -> Actor:
        if not actor.has(scope):
            raise ApiError(
                403,
                "forbidden",
                f"Scope '{scope}' is required",
                {"required_scope": scope, "current_role": actor.role},
            )
        return actor

    return Depends(dependency)
