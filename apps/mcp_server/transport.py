import uvicorn
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette

from apps.mcp_server.observability import configure_stderr_logging
from apps.mcp_server.server import mcp
from apps.mcp_server.settings import get_settings


def build_http_app() -> Starlette:
    settings = get_settings()
    allowed_hosts = [
        f"{settings.mcp_http_host}:{settings.mcp_http_port}",
        settings.mcp_http_host,
        "localhost",
    ]
    allowed_origins = [
        f"http://{settings.mcp_http_host}:{settings.mcp_http_port}",
        f"http://localhost:{settings.mcp_http_port}",
    ]
    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )
    return mcp.streamable_http_app(
        stateless_http=True, host=settings.mcp_http_host, transport_security=security
    )


def main() -> None:
    settings = get_settings()
    configure_stderr_logging()
    if settings.mcp_transport == "stdio":
        mcp.run(transport="stdio")
    else:
        uvicorn.run(
            build_http_app(),
            host=settings.mcp_http_host,
            port=settings.mcp_http_port,
            log_config=None,
        )


if __name__ == "__main__":
    main()
