# syntax=docker/dockerfile:1

# ---- Builder: resolve and install dependencies with uv --------------------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# Install dependencies first (cached layer, independent of app source changes).
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev

# Install the project itself.
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# ---- Runtime: slim image with only the built venv + source ----------------
FROM python:3.12-slim-bookworm AS runtime

# ffmpeg is required from Increment 3 onward (format decoding, US-08/US-09).
# Installed now so the image doesn't need to be rebuilt when that story lands.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 appuser
WORKDIR /app

COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --from=builder --chown=appuser:appuser /app/src /app/src

USER appuser
ENV PATH="/app/.venv/bin:$PATH" \
    HOST=0.0.0.0 \
    PORT=8000 \
    LOG_LEVEL=info

EXPOSE 8000

# Runs under uvicorn's default signal handling: SIGTERM triggers a graceful
# shutdown (in-flight requests finish, then the process exits cleanly).
CMD ["smcd-audio-transcriber"]
