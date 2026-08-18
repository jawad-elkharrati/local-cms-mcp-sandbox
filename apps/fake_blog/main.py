import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.responses import Response

from apps.fake_blog.api import articles, audit, media, system, taxonomy
from apps.fake_blog.errors import ApiError
from apps.fake_blog.web import routes as web

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fake-blog")
REQUESTS = Counter("http_requests_total", "HTTP requests", ["route", "status"])
DURATION = Histogram("http_request_duration_seconds", "HTTP request duration", ["route"])

app = FastAPI(title="Local Fake Blog API", version="1.0.0")


@app.middleware("http")
async def request_context(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except ApiError as exc:
        response = JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "request_id": request_id,
            },
        )
    except Exception:
        logger.exception("request failed request_id=%s path=%s", request_id, request.url.path)
        response = JSONResponse(
            status_code=500,
            content={
                "code": "internal_error",
                "message": "Internal local service error",
                "details": {},
                "request_id": request_id,
            },
        )
    response.headers["X-Request-ID"] = request_id
    route = request.scope.get("route")
    route_name = getattr(route, "path", request.url.path)
    REQUESTS.labels(route_name, str(response.status_code)).inc()
    DURATION.labels(route_name).observe(time.perf_counter() - start)
    return response


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health", include_in_schema=False)
async def root_health() -> dict[str, object]:
    return await system.health()


app.include_router(system.router, prefix="/api/v1")
app.include_router(articles.router, prefix="/api/v1")
app.include_router(taxonomy.router, prefix="/api/v1")
app.include_router(media.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(web.router)
