import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

TOKEN_PATTERN = re.compile(r"(?:Bearer\s+)?dev-[A-Za-z0-9._-]*token|expired-demo-token", re.I)


def redact(value: Any) -> Any:
    if isinstance(value, str):
        return TOKEN_PATTERN.sub("[REDACTED]", value)
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items() if key.lower() != "authorization"}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "service": "cms-mcp",
            "message": redact(record.getMessage()),
        }
        return json.dumps(payload, separators=(",", ":"))


def configure_stderr_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
