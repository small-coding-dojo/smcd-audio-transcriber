# ClearVoice — Audio Transcriber Service

HTTP service that accepts an uploaded audio file and returns a structured,
timestamped, speaker-diarised transcript. See [`PROJECT_BRIEF.md`](PROJECT_BRIEF.md)
for the product requirements and [`docs/`](docs/) for the
[architecture description](docs/architecture.md) (C4), the architecture
decisions ([ADR-0001](docs/adr/0001-transcription-backend.md),
[ADR-0002](docs/adr/0002-concurrency-and-resource-model.md)), the
[implementation roadmap](docs/implementation-roadmap.md), and the
[test specification](docs/test-specification.md).

**Status:** Increment 1 (project skeleton) — no transcription endpoint yet.
This README grows with each increment; see the roadmap for what's next.

---

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (dependency management and task running)
- Docker + Docker Compose (optional, for containerised runs)

## Install

```bash
uv sync
```

This creates `.venv/` and installs exact-pinned runtime and dev dependencies
from `uv.lock`.

## Run locally

```bash
uv run smcd-audio-transcriber
```

The service listens on `http://localhost:8000` by default. Configuration is
via environment variables, all with safe defaults:

| Variable | Default | Purpose |
|---|---|---|
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `8000` | Bind port |
| `LOG_LEVEL` | `info` | Python logging level |

Stop the service with `Ctrl-C` (or `SIGTERM`) — uvicorn shuts down gracefully.

## Run with Docker

```bash
docker compose up --build
```

Starts the service on `http://localhost:8000` with a single command. Override
the port or log level via a `.env` file or `PORT=9000 docker compose up`.

## Example request

Increment 1 only exposes a liveness endpoint; `POST /transcribe` arrives in
later increments (see the [roadmap](docs/implementation-roadmap.md)).

```bash
curl http://localhost:8000/
# {"service":"smcd-audio-transcriber","version":"0.1.0","status":"ok"}
```

## Development

```bash
uv run ruff check .          # lint
uv run ruff format .         # format
uv run basedpyright          # type check
```

## Project layout

```
src/smcd_audio_transcriber/   # application source
  __init__.py                 # console-script entrypoint (uvicorn runner)
  main.py                     # FastAPI app factory + routes
tests/
  generate_fixtures.py         # synthetic audio fixture generator (see docs/test-specification.md §2)
docs/                          # ADRs, roadmap, test specification
```
