# ClearVoice - Audio Transcriber Service

A Python + FastAPI service that accepts an uploaded audio file and returns a
structured, timestamped transcript with speaker diarisation. See
[PROJECT_BRIEF.md](PROJECT_BRIEF.md) for the full product requirements and
[.github/prompts/plan-audioTranscriberService.prompt.md](.github/prompts/plan-audioTranscriberService.prompt.md)
for the phased implementation plan.

> **Status: Phase 1 - Core Transcription Pipeline (batch, single-speaker
> assumption).** On top of the Phase 0 scaffolding, the service now has an
> internal audio ingestion + `faster-whisper` transcription pipeline that
> takes raw audio bytes and returns timestamped segments. This is **not yet
> exposed via an HTTP endpoint** (that's Phase 3) and **does not yet produce
> speaker labels** (that's Phase 2) - each segment's `speaker` field is
> always `None` for now.

---

## Repo structure

```
app/
  __init__.py
  main.py            # FastAPI app, health-check endpoint, request logging middleware
  config.py          # Environment-variable driven settings (pydantic-settings)
  logging_config.py  # Structured (JSON) logging, with a strict metadata-only allow-list
  models.py          # Transcript data model / API response schema (Pydantic)
  audio.py           # Audio ingestion: format/duration validation + ffmpeg normalization
  transcription.py   # faster-whisper integration (model loading + transcription)
  pipeline.py         # Internal end-to-end entry point: validate -> normalize -> transcribe
tests/
  test_health.py       # Health-check endpoint tests
  test_config.py       # Config defaults/overrides tests
  test_audio.py        # Audio validation/normalization tests (ffmpeg mocked)
  test_transcription.py  # Transcription segment-mapping tests (faster-whisper mocked)
  test_pipeline.py     # End-to-end internal pipeline tests
pyproject.toml         # Project metadata + dependency groups (base / ml / dev)
.env.example            # Documented list of all environment variables
```

## Requirements

- Python 3.11+
- [`ffmpeg`](https://ffmpeg.org/) (providing both `ffmpeg` and `ffprobe`) available on `PATH` -
  required from Phase 1 onward to validate and normalize uploaded audio. Not required to run the
  health-check endpoint or the mocked unit test suite.

## Getting started

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

All current tests (health, config, audio, transcription, pipeline) mock
`ffmpeg`/`ffprobe` and `faster-whisper` so they run without the `ml` extra or
the `ffmpeg` binary installed - see "Installing the heavy ML dependencies"
below to actually run transcription end-to-end against real audio.

### Installing the heavy ML dependencies (Phase 1+)

The `ml` extra (`faster-whisper`, `whisperx`, `pyannote.audio`, `ffmpeg-python`)
is **not** required to run the app skeleton, the health-check, or the unit
test suite, and is intentionally kept separate from the base install so the
service can be scaffolded, linted, and smoke-tested without pulling
multi-gigabyte ML dependencies. It **is** required to actually run
transcription (`app/pipeline.py`/`app/transcription.py`) against real audio.

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
| `WHISPER_MODEL_SIZE` | `base` | faster-whisper/WhisperX model size (`tiny`/`base`/`small`/`medium`/`large-v3`). Bigger = more accurate, slower, more memory. See "Transcription model" below for rationale. |
| `DEVICE` | `cpu` | Inference device (`cpu`/`cuda`). |
| `COMPUTE_TYPE` | `int8` | faster-whisper compute type, e.g. `int8` (CPU) or `float16`/`int8_float16` (GPU). |
| `WHISPER_LANGUAGE` | *(empty = auto-detect)* | ISO-639-1 code to force a language (e.g. `en`); leave unset to auto-detect per request. |
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

No model downloading happens automatically yet (no Dockerfile/build script has
been added) - `WhisperModel` will download to `MODEL_CACHE_DIR` on first use
in a dev environment with network access; that's fine for now but should be
replaced by the build-time pre-baking above before production deployment.

## Transcription model (Phase 1)

**Default model size: `base`.**

Rationale (CPU-only default, no GPU assumed - see Phase 0's open questions):

- `tiny` is fast but noticeably less accurate, especially on accented speech
  or background noise - too lossy for a service whose core value is
  transcript accuracy.
- `base` is a reasonable accuracy/latency balance on CPU with `int8` compute:
  it's roughly real-time or faster on typical CPU hardware for `int8`
  quantization, while giving materially better accuracy than `tiny`.
- `small`/`medium`/`large-v3` are meaningfully more accurate but are
  multiple times slower on CPU, which risks breaching the "reasonable
  response time" requirement for longer recordings without a GPU.
- If a GPU is confirmed available in the deployment target (open question
  from Phase 0), the recommendation would change to `small` or `medium`
  with `float16`/`int8_float16` compute for better accuracy at similar
  latency.

This is configurable via `WHISPER_MODEL_SIZE`/`DEVICE`/`COMPUTE_TYPE` without
code changes, so the default can be revisited once real hardware and audio
samples are available to benchmark against.

**Language detection: auto-detect by default (`WHISPER_LANGUAGE` unset).**

Rationale:

- The product brief doesn't restrict the service to English-only content,
  and `faster-whisper`'s auto-detection only inspects the first ~30 seconds
  of audio, so the latency cost is small and bounded regardless of total
  recording length.
- Forcing a language is still supported (`WHISPER_LANGUAGE=en`) for
  deployments that know their audio is always a single, known language and
  want to skip the detection pass and avoid rare misdetection on short/noisy
  clips.

**Model loading:** the `faster-whisper` model is loaded once per process
(cached via `functools.lru_cache` in `app/transcription.py`) and reused
across requests rather than reloaded per request, since loading is expensive
relative to a single transcription call. A bounded worker pool to run
inference off the event loop and to cap concurrent jobs is introduced in
Phase 5.

## Audio ingestion & normalization (Phase 1)

`app/audio.py` implements two validation layers before/around invoking
`ffmpeg`:

1. **Cheap early rejection** - `validate_extension_and_content_type` checks
   the uploaded filename's extension and/or the declared content-type against
   an allow-list of common audio formats/containers, and rejects anything
   else immediately with a clear error - before any subprocess is spawned.
2. **Authoritative validation via `ffprobe`/`ffmpeg`** - the file is probed
   for a decodable duration (rejecting corrupt/unreadable files and
   zero-duration streams) and checked against `MAX_AUDIO_DURATION_SECONDS`,
   then converted to 16kHz mono WAV bytes via `ffmpeg`.

**Temp file handling:** the raw upload is written to exactly one OS temp
file (needed because `ffmpeg`/`ffprobe` require a seekable path for several
container formats), and that file is deleted in a `finally` block - so it is
removed whether validation passes, fails, or `ffmpeg` raises partway through.
The normalized WAV output is returned as in-memory bytes and never touches
disk.

The internal pipeline (`app/pipeline.py`, `transcribe_audio_upload`) wires
validation -> normalization -> transcription together; it is not yet called
from an HTTP endpoint (see Phase 3).

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
