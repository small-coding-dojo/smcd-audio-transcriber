"""ClearVoice Audio Transcriber Service."""

import logging
import os

import uvicorn

__version__ = "0.1.0"


def main() -> None:
    """Console-script entrypoint: `smcd-audio-transcriber` or `uv run smcd-audio-transcriber`.

    Reads HOST/PORT/LOG_LEVEL from the environment with safe defaults so the
    same image works locally and in docker-compose without code changes.
    Uvicorn handles SIGTERM/SIGINT with a graceful shutdown by default,
    satisfying US-01's "process exits cleanly on SIGTERM" requirement.
    """
    log_level = os.environ.get("LOG_LEVEL", "info").lower()
    logging.basicConfig(level=log_level.upper())

    uvicorn.run(
        "smcd_audio_transcriber.main:app",
        host=os.environ.get("HOST", "0.0.0.0"),  # container-bound service by design
        port=int(os.environ.get("PORT", "8000")),
        log_level=log_level,
    )


if __name__ == "__main__":
    main()
