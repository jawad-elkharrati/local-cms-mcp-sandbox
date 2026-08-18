import time
from collections.abc import Awaitable, Callable
from typing import Any

from prometheus_client import Counter, Histogram

from apps.mcp_server.errors import BlogApiError

TOOL_CALLS = Counter("mcp_tool_calls_total", "MCP tool calls", ["tool", "outcome"])
TOOL_DURATION = Histogram("mcp_tool_duration_seconds", "MCP tool duration", ["tool"])


async def safe(call: Callable[[], Awaitable[dict[str, Any]]]) -> dict[str, Any]:
    name = getattr(call, "__name__", "operation")
    started = time.perf_counter()
    try:
        result = await call()
        TOOL_CALLS.labels(name, "success").inc()
        return result
    except BlogApiError as exc:
        TOOL_CALLS.labels(name, exc.code).inc()
        return exc.as_result()
    finally:
        TOOL_DURATION.labels(name).observe(time.perf_counter() - started)
