from io import BytesIO

import anyio
from minio import Minio

from apps.fake_blog.settings import get_settings

_TEST_OBJECTS: dict[str, bytes] = {}


class ObjectStorage:
    def __init__(self) -> None:
        self.settings = get_settings()

    def _client(self) -> Minio:
        return Minio(
            self.settings.minio_endpoint,
            access_key=self.settings.minio_access_key,
            secret_key=self.settings.minio_secret_key,
            secure=self.settings.minio_secure,
        )

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        if self.settings.app_env == "test":
            _TEST_OBJECTS[key] = data
            return

        def operation() -> None:
            client = self._client()
            if not client.bucket_exists(self.settings.minio_bucket):
                client.make_bucket(self.settings.minio_bucket)
            client.put_object(
                self.settings.minio_bucket,
                key,
                BytesIO(data),
                len(data),
                content_type=content_type,
            )

        await anyio.to_thread.run_sync(operation)

    async def get(self, key: str) -> bytes:
        if self.settings.app_env == "test":
            return _TEST_OBJECTS[key]

        def operation() -> bytes:
            response = self._client().get_object(self.settings.minio_bucket, key)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()

        return await anyio.to_thread.run_sync(operation)

    async def health(self) -> bool:
        if self.settings.app_env == "test":
            return True
        try:
            return await anyio.to_thread.run_sync(
                lambda: self._client().bucket_exists(self.settings.minio_bucket)
            )
        except Exception:
            return False
