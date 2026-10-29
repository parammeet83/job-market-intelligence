"""FastAPI application: the public, read-only JobMarket Pulse API.

Run locally:  uv run uvicorn backend.app.main:app --reload
On Vercel the same `app` object is the function entrypoint (pyproject [tool.vercel]).
"""

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeout

from backend.app.api import exports, v1
from backend.app.database import DatabaseNotConfigured, get_engine
from backend.app.schemas import Health
from backend.core.config import get_settings
from backend.core.logging import configure_logging, log_event, safe_error_summary

VERSION = "0.1.0"
settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("backend.api")

app = FastAPI(
    title="JobMarket Pulse API",
    version=VERSION,
    summary="Read-only analytics over an automatically collected, historical job-listing dataset.",
    description=(
        "All endpoints are read-only (GET). Data comes from public job APIs whose terms permit "
        "this use; see /api/v1/sources for attribution. Missing values are reported as null, "
        "never as zero."
    ),
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "HEAD", "OPTIONS"],
    allow_headers=["Accept", "Content-Type"],
    allow_credentials=False,
    max_age=600,
)


@app.middleware("http")
async def request_log(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = uuid.uuid4().hex[:12]
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.url.path.startswith("/api/v1") and request.method == "GET":
        response.headers.setdefault("Cache-Control", "public, max-age=60, s-maxage=300")
    log_event(
        logger,
        "request",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        ms=round((time.perf_counter() - started) * 1000, 1),
    )
    return response


@app.exception_handler(DatabaseNotConfigured)
async def db_not_configured(_: Request, __: Exception) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": "Database is not configured."})


@app.exception_handler(OperationalError)
@app.exception_handler(PoolTimeout)
async def db_unavailable(_: Request, exc: Exception) -> JSONResponse:
    log_event(logger, "database unavailable", logging.ERROR, error=safe_error_summary(exc))
    return JSONResponse(
        status_code=503,
        content={"detail": "Database temporarily unavailable. Please retry."},
        headers={"Retry-After": "10", "Cache-Control": "no-store"},
    )


@app.exception_handler(DBAPIError)
async def db_error(_: Request, exc: Exception) -> JSONResponse:
    log_event(logger, "database error", logging.ERROR, error=safe_error_summary(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error."},
        headers={"Cache-Control": "no-store"},
    )


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    # Echo field locations and messages only, never the submitted values.
    errors = [
        {"loc": list(e.get("loc", ())), "msg": e.get("msg", "invalid")} for e in exc.errors()[:10]
    ]
    return JSONResponse(
        status_code=422, content={"detail": errors}, headers={"Cache-Control": "no-store"}
    )


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception) -> JSONResponse:
    log_event(logger, "unhandled error", logging.ERROR, error=safe_error_summary(exc))
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


@app.get("/api/v1/health", response_model=Health, tags=["meta"], summary="Liveness and DB check")
def health(response: Response) -> Health:
    response.headers["Cache-Control"] = "no-store"
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return Health(status="ok", database="ok", version=VERSION)
    except DatabaseNotConfigured:
        return Health(status="degraded", database="not_configured", version=VERSION)
    except Exception as exc:
        log_event(logger, "health check failed", logging.WARNING, error=safe_error_summary(exc))
        return Health(status="degraded", database="unavailable", version=VERSION)


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {"name": "JobMarket Pulse API", "docs": "/api/docs", "health": "/api/v1/health"}


app.include_router(v1.router, prefix="/api/v1", tags=["analytics"])
app.include_router(exports.router, prefix="/api/v1")
