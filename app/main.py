"""FastAPI application entrypoint.

Phase 0 scope: app skeleton, health-check endpoint, config wiring, and
structured metadata-only request logging. No transcription/ML inference
logic lives here yet (see Phase 1+).
"""

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.config import get_settings
from app.logging_config import configure_logging

settings = get_settings()
configure_logging(settings.log_level)

logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # NOTE: no model loading here yet (Phase 0 = scaffolding only). Once
    # transcription is introduced (Phase 1), the model should be loaded once
    # here and shared across requests rather than reloaded per-request.
    logger.info("service_starting", extra={"event": "startup"})
    yield
    logger.info("service_stopping", extra={"event": "shutdown"})


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log request metadata only - never bodies, headers with content, or
    query strings that might carry user data. See app/logging_config.py.
    """
    request_id = str(uuid.uuid4())
    start = time.perf_counter()

    response = await call_next(request)

    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    logger.info(
        "request_completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/health", tags=["health"])
async def health() -> dict:
    """Liveness/readiness check. Returns 200 once the app has started."""
    return {"status": "ok"}
