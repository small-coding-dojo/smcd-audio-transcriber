# ADR-0001: Transcription Backend Selection

**Date:** 2026-06-22
**Status:** Approved
**Deciders:** Engineering

---

## Context

ClearVoice requires an HTTP service that accepts an uploaded audio file and returns a structured transcript with timestamps and speaker labels. The brief imposes a privacy constraint: uploaded audio must never be stored, logged, or retained after the response is sent — neither by this service nor by any third party without equivalent no-retention guarantees. The service must also handle German-language audio and respond within a reasonable time relative to audio length.

---

## Decision Drivers

- Audio must not be stored, logged, or retained beyond the request — by this service or any third party
- Must support German language with accuracy sufficient for most clear recordings
- Transcript must include per-segment timestamps and speaker identification

---

## Options Considered

### Comparison Table

| Option | German accuracy | Timestamps | Diarisation | Data retention risk | Operational overhead |
|---|---|---|---|---|---|
| **faster-whisper + pyannote** | Excellent (large-v3) | Segment + word | Yes (via pyannote) | None — fully self-hosted | Medium — two models, HF token |
| **whisperx** | Excellent | Word-level (forced alignment) | Yes (bundled) | None — fully self-hosted | Low (one library) — but less control |
| **OpenAI Whisper (original)** | Excellent | Segment + word | No | None — fully self-hosted | Low — but ~4× slower than faster-whisper; no diarisation |
| **OpenAI Whisper API (cloud)** | Excellent | Segment only | No | Conditional — zero-data-retention policy must be verified and contractually agreed | Very low |
| **AssemblyAI (cloud)** | Good | Word-level | Yes | Conditional — zero-data-retention tier available; must be verified | Very low |
| **Deepgram (cloud)** | Good (Nova-2) | Word-level | Yes | Conditional — zero-data-retention policy must be verified and contractually agreed | Very low |
| **Google Speech-to-Text v2** | Excellent (Chirp) | Word-level | Yes | Conditional — DPA and data processing terms must be verified | Low — vendor lock-in risk |

### Pros and Cons

#### faster-whisper + pyannote.audio (chosen)

| Pros | Cons |
|---|---|
| Best-in-class German accuracy with `large-v3` model | Requires HuggingFace account + accepted model license for pyannote |
| ~4× faster and ~50% less memory than original Whisper | Two separate models to load and manage |
| No audio ever leaves the service boundary | Diarisation–transcript alignment must be written manually (~10–20 lines) |
| Word-level timestamps available | Startup time higher than cloud clients (model loading) |
| Active maintenance; CTranslate2 backend supports CPU int8, CUDA, Metal | pyannote diarisation adds ~1–3 s latency overhead per file |

#### whisperx

| Pros | Cons |
|---|---|
| Bundles faster-whisper + alignment + pyannote into one API | Less actively maintained; pinned transitive deps cause conflicts |
| Word-level timestamps with speaker labels out of the box | Less control over model versions and concurrency behaviour |
| Reduces integration code | Harder to tune individual components |

#### Cloud APIs (OpenAI, AssemblyAI, Deepgram, Google)

| Pros | Cons |
|---|---|
| Zero model management | Audio leaves the machine — retention policy must be contractually verified before use |
| Managed reliability | Ongoing per-request cost |
| Some offer streaming and diarisation out of the box | Network latency added to every request |
| No GPU/infrastructure required | Vendor dependency; harder to audit data handling |

---

## Decision

**Proposed: faster-whisper (`large-v3`) for transcription combined with pyannote.audio (`pyannote/speaker-diarization-3.1`) for speaker diarisation.**

Self-hosted models are preferred because they eliminate data retention risk by design — no contractual verification required, and no audio ever leaves the service boundary. Cloud APIs remain viable if a zero-retention policy can be contractually confirmed, but that adds a procurement and compliance dependency that self-hosting avoids.

`whisperx` is not proposed over the manual combination because it gives less control over model versions and is less actively maintained.

---

## Consequences

- A HuggingFace token (`HF_TOKEN`) and one-time license acceptance for `pyannote/speaker-diarization-3.1` is an operational prerequisite.
- A GPU is strongly recommended for production latency targets; CPU-only deployments should use `int8` quantization via CTranslate2.
- Any temporary files written during processing (e.g., for format conversion) must be deleted before the response is returned — audio must not persist on disk beyond the request lifecycle.
- Startup time will be several seconds while models load — this is a one-time cost per process.
