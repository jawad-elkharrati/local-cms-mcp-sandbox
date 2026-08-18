import asyncio

from sqlalchemy import text

from apps.fake_blog.db.session import engine


async def reset() -> None:
    async with engine.begin() as connection:
        await connection.execute(text("DROP SCHEMA public CASCADE"))
        await connection.execute(text("CREATE SCHEMA public"))


def main() -> None:
    asyncio.run(reset())


if __name__ == "__main__":
    main()
