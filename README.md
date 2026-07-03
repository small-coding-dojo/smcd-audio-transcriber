# ClearVoice - Audio Transcriber Service

A Python + FastAPI service that accepts an uploaded audio file and returns a
structured, timestamped transcript with speaker diarisation. See
[PROJECT_BRIEF.md](PROJECT_BRIEF.md) for the full product requirements and
[.github/prompts/plan-audioTranscriberService.prompt.md](.github/prompts/plan-audioTranscriberService.prompt.md)
for the phased implementation plan.

> **Status: Phase 0 - Scaffolding & Project Setup.** This is project skeleton
> only: a FastAPI app with a health-check endpoint, environment-driven
> configuration, and structured logging wiring. There is no transcription or
> diarisation logic yet - that lands in later phases.

---

## Repo structure

```
app/
  __init__.py
  main.py            # FastAPI app, health-check endpoint, request logging middleware
  config.py          # Environment-variable driven settings (pydantic-settings)
  logging_config.py  # Structured (JSON) logging, with a strict metadata-only allow-list
tests/
  test_health.py      # Health-check endpoint tests
  test_config.py      # Config defaults/overrides tests
pyproject.toml         # Project metadata + dependency groups (base / ml / dev)
.env.example            # Documented list of all environment variables
```

## Requirements

- Python 3.11+
- [`ffmpeg`](https://ffmpeg.org/) available on `PATH` (needed from Phase 1 onward for audio
  format normalization; not required to run the Phase 0 skeleton).

## Getting started (Phase 0 skeleton only)

```bash
python -m venv .venv
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# macOS/Linux
source .venv/bin/activate

pip install -e ".[dev]"

uvicorn app.main:app --reload
```

Then check:

```bash
curl http://127.0.0.1:8000/health
# {"status":"ok"}
```

Run the test suite:

```bash
pytest
```

### Installing the heavy ML dependencies (Phase 1+)

The `ml` extra (`faster-whisper`, `whisperx`, `pyannote.audio`, `ffmpeg-python`)
is **not** required to run the Phase 0 skeleton and is intentionally kept
separate from the base install so the service can be scaffolded, linted, and
smoke-tested without pulling multi-gigabyte ML dependencies.

```bash
# CPU-only (default): just install the extra, pip will resolve a CPU torch build.
pip install -e ".[ml]"

# GPU: install a CUDA-matched torch/torchaudio build FIRST (see
# https://pytorch.org/get-started/locally/ for the correct index URL for your
# CUDA version), then install the ml extra so it reuses that torch install
# instead of pulling in a CPU wheel:
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install -e ".[ml]"
```

## Configuration

All configuration is environment-variable driven (via `pydantic-settings`),
with defaults suitable for local CPU development. Copy `.env.example` to
`.env` and adjust as needed; unset variables fall back to the defaults below.

| Variable | Default | Description |
|---|---|---|
| `APP_NAME` | `ClearVoice Audio Transcriber Service` | Display name used in the FastAPI app metadata. |
| `LOG_LEVEL` | `INFO` | Python logging level. |
| `WHISPER_MODEL_SIZE` | `base` | faster-whisper/WhisperX model size (`tiny`/`base`/`small`/`medium`/`large-v3`). Bigger = more accurate, slower, more memory. |
| `DEVICE` | `cpu` | Inference device (`cpu`/`cuda`). |
| `COMPUTE_TYPE` | `int8` | faster-whisper compute type, e.g. `int8` (CPU) or `float16`/`int8_float16` (GPU). |
| `MAX_CONCURRENT_JOBS` | `2` | Max number of simultaneous transcription/diarisation jobs (bounded worker pool, wired up in Phase 5). |
| `MAX_UPLOAD_SIZE_MB` | `100` | Max accepted upload size in megabytes. |
| `MAX_AUDIO_DURATION_SECONDS` | `1800` | Max accepted audio duration in seconds (default 30 minutes). |
| `HUGGINGFACE_TOKEN` | *(empty)* | Token required by pyannote.audio's pretrained diarisation pipelines. Reserved for Phase 2 - never commit a real value. |
| `MODEL_CACHE_DIR` | `/models` | Directory models are loaded from (see caching strategy below). |

## Model download & caching strategy

**Decision:** models are pre-baked into the container image at build time,
not downloaded on first run.

Rationale:

- Avoids any runtime network call to HuggingFace/model hosts when handling a
  transcription request, which is important both for latency (no cold-start
  download of multi-GB model weights) and for the privacy story (a
  request-handling path that never needs outbound network access is easier to
  reason about and to lock down, e.g. via egress policy).
- Keeps container startup deterministic and reproducible across environments.

Planned mechanics (wired up when a Dockerfile is introduced, see open
questions below):

1. During the image build, run a small script that downloads the configured
   `WHISPER_MODEL_SIZE` faster-whisper/WhisperX model weights and the
   pyannote.audio diarisation pipeline into `MODEL_CACHE_DIR`.
2. Set `HF_HUB_OFFLINE=1` (and equivalent faster-whisper/CTranslate2 options)
   at runtime so libraries fail fast instead of silently reaching out to the
   network if a model is missing from the cache.
3. `MODEL_CACHE_DIR` is the single source of truth both at build time (where
   it's populated) and at runtime (where it's read from) - keeping it
   configurable allows mounting a pre-populated volume as an alternative to
   baking it into the image, if that's preferred in a given deployment.

No model downloading happens in Phase 0 - there is no ML inference code yet.

## Privacy & logging

Per the project brief, uploaded audio and transcript text must never be
stored or logged. This is enforced in code today via
[app/logging_config.py](app/logging_config.py):

- All log output goes through a `JsonFormatter` that only emits an
  **allow-listed** set of metadata fields (request id, HTTP method/path,
  status code, duration, file size, audio duration). Any other field is
  silently dropped rather than logged.
- The request-logging middleware in [app/main.py](app/main.py) only logs
  metadata about each request/response (method, path, status, duration) -
  never bodies, headers with content, or query strings.

This rule must continue to hold as later phases add transcription/diarisation
logging: log *facts about* a request (duration, file size, status), never the
audio bytes, the file path if it embeds user data, or the transcript text
itself.

## Open questions (flagged, not blocking Phase 0)

- **Docker vs bare-metal deployment target:** not yet decided. No Dockerfile
  is included yet. Once decided, the Dockerfile should implement the model
  pre-baking strategy described above.
- **GPU vs CPU-only assumption:** defaults currently assume CPU-only
  (`DEVICE=cpu`, `WHISPER_MODEL_SIZE=base`, `COMPUTE_TYPE=int8`). If GPU is
  available in the target environment, the default model size and compute
  type should likely change (e.g. a larger model with `float16`/`int8_float16`
  for better accuracy at similar latency).

## Roadmap

See [.github/prompts/plan-audioTranscriberService.prompt.md](.github/prompts/plan-audioTranscriberService.prompt.md)
for the full phased plan (transcription, diarisation, API contract, privacy
audit, concurrency/performance, edge cases, testing, docs, and the streaming
stretch goal).
