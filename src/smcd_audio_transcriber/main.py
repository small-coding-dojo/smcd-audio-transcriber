"""FastAPI application entrypoint for the ClearVoice Audio Transcriber Service.

Increment 1 (project skeleton) provides only a liveness endpoint. The
`/transcribe` endpoint (US-03) and `/health` readiness check (US-02) are
added in later increments per docs/implementation-roadmap.md.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

logger = logging.getLogger("smcd_audio_transcriber")

SERVICE_NAME = "smcd-audio-transcriber"
SERVICE_VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Log process start/stop. Never logs request or audio content (REQ-PRIV)."""
    logger.info("%s v%s starting up", SERVICE_NAME, SERVICE_VERSION)
    try:
        yield
    finally:
        logger.info("%s shutting down", SERVICE_NAME)


def create_app() -> FastAPI:
    """Application factory, so tests can construct isolated instances."""
    app = FastAPI(
        title="ClearVoice Audio Transcriber Service",
        version=SERVICE_VERSION,
        lifespan=lifespan,
    )

    @app.get("/")
    async def root() -> dict[str, str]:
        """Liveness endpoint confirming the process is up and serving requests."""
        return {"service": SERVICE_NAME, "version": SERVICE_VERSION, "status": "ok"}

    return app


app = create_app()
