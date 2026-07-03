"""Structured logging setup.

STRICT PRIVACY RULE (see PROJECT_BRIEF.md and README "Privacy & logging"):
Logs may only ever contain *metadata* - things like request id, HTTP method/
path, status code, duration, file size, audio duration. Logs must NEVER
contain:
  - raw audio bytes or audio file contents
  - transcript text
  - file paths that embed user-supplied data (e.g. original filenames)

Only fields in `_ALLOWED_EXTRA_KEYS` below are emitted from the structured
`extra={...}` payload passed to log calls. When adding a new field, add it to
that allow-list deliberately and confirm it cannot carry user content.
"""

import json
import logging
import sys
from datetime import datetime, timezone

_ALLOWED_EXTRA_KEYS = {
    "event",
    "request_id",
    "method",
    "path",
    "status_code",
    "duration_ms",
    "file_size_bytes",
    "audio_duration_seconds",
}


class JsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON with an allow-listed field set."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in _ALLOWED_EXTRA_KEYS:
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging to emit allow-listed, JSON-structured log lines."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    # Third-party access logs can be noisy and, in uvicorn's default format,
    # include the request path - keep at WARNING to reduce accidental
    # exposure of query strings/paths beyond what our own logger emits.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
