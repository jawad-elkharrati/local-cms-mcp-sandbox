import asyncio
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from apps.fake_blog.db.models import Base
from apps.fake_blog.db.session import engine
from apps.fake_blog.main import app
from scripts.seed import seed


async def prepare_database() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    await seed()


@pytest.fixture(scope="session", autouse=True)
def database() -> Iterator[None]:
    asyncio.run(prepare_database())
    yield
    asyncio.run(engine.dispose())


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as value:
        yield value


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
