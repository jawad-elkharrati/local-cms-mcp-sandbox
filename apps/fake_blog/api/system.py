from fastapi import APIRouter, Depends
from redis.asyncio import from_url
from sqlalchemy import text

from apps.fake_blog.auth import Actor, get_actor
from apps.fake_blog.db.session import engine
from apps.fake_blog.domain.storage import ObjectStorage
from apps.fake_blog.settings import get_settings

router = APIRouter(tags=["system"])


@router.get("/health")
async def health() -> dict[str, object]:
    dependencies: dict[str, str] = {}
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        dependencies["database"] = "ok"
    except Exception:
        dependencies["database"] = "unavailable"
    if get_settings().app_env == "test":
        dependencies["redis"] = "ok"
    else:
        redis = from_url(get_settings().redis_url)
        try:
            dependencies["redis"] = "ok" if await redis.ping() else "unavailable"
        except Exception:
            dependencies["redis"] = "unavailable"
        finally:
            await redis.aclose()
    dependencies["minio"] = "ok" if await ObjectStorage().health() else "unavailable"
    overall = "ok" if all(value == "ok" for value in dependencies.values()) else "degraded"
    return {"status": overall, "service": "fake-blog", "dependencies": dependencies}


@router.get("/me")
async def me(actor: Actor = Depends(get_actor)) -> dict[str, object]:
    return {
        "id": actor.id,
        "email": actor.email,
        "display_name": actor.display_name,
        "role": actor.role,
        "scopes": sorted(actor.scopes),
    }


@router.get("/permissions")
async def permissions(actor: Actor = Depends(get_actor)) -> dict[str, object]:
    return {
        "role": actor.role,
        "scopes": sorted(actor.scopes),
        "can_publish": actor.has("article:publish"),
        "can_admin": actor.has("audit:read"),
    }


@router.get("/capabilities")
async def capabilities(actor: Actor = Depends(get_actor)) -> dict[str, object]:
    return {
        "api_version": "1.0",
        "local_only": True,
        "features": ["articles", "revisions", "taxonomy", "media", "audit", "tfidf"],
        "role": actor.role,
    }
