import asyncio

from sqlalchemy import text

from apps.fake_blog.db.session import engine

EXPECTED = {
    "users": 4,
    "api_tokens": 5,
    "articles": 14,
    "tags": 11,
    "categories": 5,
    "media_assets": 4,
}


async def verify() -> None:
    async with engine.connect() as connection:
        for table, expected in EXPECTED.items():
            count = await connection.scalar(text(f"SELECT COUNT(*) FROM {table}"))  # noqa: S608
            if count != expected:
                raise RuntimeError(f"{table}: expected {expected}, got {count}")
            print(f"{table}={count}")


def main() -> None:
    asyncio.run(verify())


if __name__ == "__main__":
    main()
