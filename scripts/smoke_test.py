import asyncio
import os

import httpx


async def smoke() -> None:
    base_url = os.getenv("BLOG_PUBLIC_BASE_URL", "http://127.0.0.1:8000")
    token = os.getenv("BLOG_API_TOKEN", "dev-editor-token")
    async with httpx.AsyncClient(base_url=base_url, timeout=10) as client:
        health = await client.get("/health")
        health.raise_for_status()
        identity = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
        identity.raise_for_status()
        listing = await client.get(
            "/api/v1/articles", headers={"Authorization": f"Bearer {token}"}, params={"limit": 5}
        )
        listing.raise_for_status()
        public = await client.get("/")
        public.raise_for_status()
    print(f"Smoke passed: role={identity.json()['role']} articles={len(listing.json()['items'])}")


def main() -> None:
    asyncio.run(smoke())


if __name__ == "__main__":
    main()
