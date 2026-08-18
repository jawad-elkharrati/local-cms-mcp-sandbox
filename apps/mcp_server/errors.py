from typing import Any


class BlogApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any],
        request_id: str | None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        self.request_id = request_id

    def as_result(self) -> dict[str, Any]:
        guidance = {
            401: "Check the configured fake local token.",
            403: "Inspect get_permissions; credentials are never escalated.",
            409: "Re-read the article and retry deliberately with its current version.",
            503: "Check the local Fake Blog dependencies.",
        }.get(self.status_code)
        return {
            "ok": False,
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
                "request_id": self.request_id,
                "recoverable": self.status_code in {409, 429, 503},
                "guidance": guidance,
            },
        }


class DependencyUnavailable(BlogApiError):
    def __init__(self, message: str) -> None:
        super().__init__(503, "dependency_unavailable", message, {}, None)
