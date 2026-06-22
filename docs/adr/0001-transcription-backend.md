# ADR-0001: Transcription Backend Selection

**Date:** 2026-06-22
**Status:** Accepted
**Deciders:** Engineering

---

## Context

ClearVoice requires an HTTP service that accepts an uploaded audio file and returns a structured transcript with timestamps and speaker labels. The brief imposes a hard privacy constraint: uploaded audio must never be written to disk or sent to external systems. The service must also handle German-language audio, support concurrent requests, and respond within a reasonable time relative to audio length.

---

## Decision Drivers

- Audio must be processed entirely in memory — no disk writes, no third-party uploads
- Must support German language with accuracy sufficient for most clear recordings
- Transcript must include per-segment timestamps and speaker identification
- Must handle concurrent HTTP requests without degrading
- Must be efficient with CPU/GPU memory

---

## Options Considered

### Comparison Table

| Option | German accuracy | Timestamps | Diarisation | In-memory | Privacy-safe | Concurrency | Operational overhead |
|---|---|---|---|---|---|---|---|
| **faster-whisper + pyannote** | Excellent (large-v3) | Segment + word | Yes (via pyannote) | Yes | Yes (self-hosted) | Worker pool required | Medium — two models, HF token |
| **whisperx** | Excellent | Word-level (forced alignment) | Yes (bundled) | Yes | Yes (self-hosted) | Worker pool required | Low (one library) — but less control |
| **OpenAI Whisper (original)** | Excellent | Segment + word | No | Yes | Yes (self-hosted) | Worker pool required | Low — but ~4× slower than faster-whisper |
| **OpenAI Whisper API (cloud)** | Excellent | Segment only | No | N/A | **No** — audio uploaded externally | Managed by provider | Very low |
| **AssemblyAI (cloud)** | Good | Word-level | Yes | N/A | **No** — audio uploaded externally | Managed by provider | Very low |
| **Deepgram (cloud)** | Good (Nova-2) | Word-level | Yes | N/A | **No** — audio uploaded externally | Managed by provider | Very low |
| **Google Speech-to-Text v2** | Excellent (Chirp) | Word-level | Yes | N/A | **No** — audio uploaded externally | Managed by provider | Low — but vendor lock-in |

### Pros and Cons

#### faster-whisper + pyannote.audio (chosen)

| Pros | Cons |
|---|---|
| Best-in-class German accuracy with `large-v3` model | Requires HuggingFace account + accepted model license for pyannote |
| ~4× faster and ~50% less memory than original Whisper | Two separate models to load and manage |
| Fully in-memory pipeline (numpy/BytesIO) | Diarisation–transcript alignment must be written manually (~10–20 lines) |
| No audio leaves the machine | GPU memory contention under high concurrency requires a worker pool or queue |
| Word-level timestamps available | Startup time higher than cloud clients (model loading) |
| Active maintenance; CTranslate2 backend supports CPU int8, CUDA, Metal | pyannote diarisation adds ~1–3 s overhead per file |
| Model shared across threads safely | |

#### whisperx

| Pros | Cons |
|---|---|
| Bundles faster-whisper + alignment + pyannote into one API | Less actively maintained; pinned transitive deps cause conflicts |
| Word-level timestamps with speaker labels out of the box | Less control over model versions and concurrency behaviour |
| Reduces integration code | Harder to tune individual components |

#### Cloud APIs (OpenAI, AssemblyAI, Deepgram, Google)

| Pros | Cons |
|---|---|
| Zero model management | **Audio leaves the machine** — violates the privacy requirement |
| Built-in concurrency | Ongoing per-request cost |
| Managed reliability | Network latency added to every request |
| Some offer streaming | Vendor dependency |

---

## Decision

**Use faster-whisper (`large-v3`) for transcription combined with pyannote.audio (`pyannote/speaker-diarization-3.1`) for speaker diarisation.**

The pipeline will be:

1. Accept audio bytes from the HTTP request body
2. Decode to a numpy float32 array in memory using `pydub` or `soundfile` (via `io.BytesIO`) — no disk write
3. Run `faster-whisper` transcription to obtain segments with timestamps
4. Run `pyannote.audio` diarisation on the same in-memory audio tensor
5. Merge diarisation speaker windows with transcript segments
6. Return structured JSON

Both models are loaded once at service startup and shared across requests. Concurrent requests are handled via a bounded worker pool (e.g., `asyncio` + `ThreadPoolExecutor`) to prevent GPU memory exhaustion.

Cloud APIs are explicitly ruled out by the privacy requirement. `whisperx` is not chosen because the manual combination gives equivalent functionality with better control over model versions, concurrency, and in-memory handling.

---

## Consequences

- A HuggingFace token (`HF_TOKEN`) and one-time license acceptance for `pyannote/speaker-diarization-3.1` is an operational prerequisite.
- A GPU is strongly recommended for production latency targets; CPU-only deployments should use `int8` quantization via CTranslate2.
- The service must implement a worker queue or semaphore to cap concurrent in-flight model calls and prevent OOM under load.
- Audio format diversity (mp3, m4a, ogg, wav, etc.) is handled by `pydub`/`ffmpeg` decoding to PCM in memory before passing to the models.
- Startup time will be several seconds while models load — this is a one-time cost per process.
