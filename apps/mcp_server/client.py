import uuid
from pathlib import Path
from typing import Any

import anyio
import httpx

from apps.mcp_server.errors import BlogApiError, DependencyUnavailable
from apps.mcp_server.settings import MCPSettings, get_settings


class BlogApiClient:
    def __init__(
        self,
        settings: MCPSettings | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._client = httpx.AsyncClient(
            base_url=self.settings.blog_api_base_url,
            headers={"Authorization": f"Bearer {self.settings.blog_api_token}"},
            timeout=httpx.Timeout(10.0, connect=3.0),
            transport=transport,
        )

    async def __aenter__(self) -> "BlogApiClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        files: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        request_id = str(uuid.uuid4())
        safe_headers = {"X-Request-ID": request_id, **(headers or {})}
        try:
            response = await self._client.request(
                method, path, params=params, json=json, headers=safe_headers, files=files, data=data
            )
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise DependencyUnavailable(
                f"Fake Blog API unavailable ({type(exc).__name__})"
            ) from exc
        returned_request_id = response.headers.get("X-Request-ID", request_id)
        if response.status_code >= 400:
            try:
                body = response.json()
            except ValueError:
                body = {
                    "code": "internal_error",
                    "message": "Invalid API error response",
                    "details": {},
                }
            raise BlogApiError(
                response.status_code,
                str(body.get("code", "internal_error")),
                str(body.get("message", "API request failed")),
                body.get("details") if isinstance(body.get("details"), dict) else {},
                returned_request_id,
            )
        if response.status_code == 204:
            return {"ok": True, "request_id": returned_request_id}
        result = response.json()
        if isinstance(result, dict):
            result.setdefault("request_id", returned_request_id)
            return result
        return {"data": result, "request_id": returned_request_id}

    async def get(self, path: str, **params: Any) -> dict[str, Any]:
        return await self.request(
            "GET", path, params={key: value for key, value in params.items() if value is not None}
        )

    async def create_article(
        self, payload: dict[str, Any], idempotency_key: str | None = None
    ) -> dict[str, Any]:
        headers = {"Idempotency-Key": idempotency_key or str(uuid.uuid4())}
        return await self.request("POST", "/articles", json=payload, headers=headers)

    async def upload_media(
        self, local_path: str, alt_text: str | None, caption: str | None
    ) -> dict[str, Any]:
        path, is_file, size = await anyio.to_thread.run_sync(
            lambda: (
                Path(local_path).resolve(),
                Path(local_path).resolve().is_file(),
                Path(local_path).resolve().stat().st_size
                if Path(local_path).resolve().is_file()
                else 0,
            )
        )
        if not is_file:
            raise BlogApiError(
                400,
                "validation_error",
                "local_path must be a regular file",
                {"local_path": str(path)},
                None,
            )
        if size > 10 * 1024 * 1024:
            raise BlogApiError(413, "upload_too_large", "Local file exceeds 10 MiB", {}, None)
        content = await anyio.to_thread.run_sync(path.read_bytes)
        return await self.request(
            "POST",
            "/media",
            files={"file": (path.name, content)},
            data={"alt_text": alt_text or "", "caption": caption or ""},
        )
