import logging

import pytest
from pydantic import ValidationError
from starlette.testclient import TestClient

from apps.mcp_server.observability import JsonFormatter, redact
from apps.mcp_server.settings import MCPSettings
from apps.mcp_server.transport import build_http_app


def test_redaction_removes_fake_token_values() -> None:
    assert redact("Authorization: Bearer dev-editor-token") == "Authorization: [REDACTED]"
    record = logging.LogRecord(
        "test", logging.INFO, __file__, 1, "token=%s", ("dev-admin-token",), None
    )
    assert "dev-admin-token" not in JsonFormatter().format(record)


def test_http_configuration_rejects_public_bind() -> None:
    with pytest.raises(ValidationError):
        MCPSettings(_env_file=None, mcp_http_host="0.0.0.0")  # noqa: S104


def test_invalid_origin_is_forbidden() -> None:
    with TestClient(build_http_app()) as client:
        response = client.post(
            "/mcp",
            headers={
                "Host": "127.0.0.1:8100",
                "Origin": "https://attacker.invalid",
                "Content-Type": "application/json",
                "MCP-Protocol-Version": "2026-07-28",
            },
            json={"jsonrpc": "2.0", "id": 1, "method": "server/discover", "params": {}},
        )
    assert response.status_code == 403
