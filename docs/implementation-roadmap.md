# Implementation Roadmap — Audio Transcriber Service

**Date:** 2026-06-29  
**Linked brief:** [PROJECT_BRIEF.md](../PROJECT_BRIEF.md)  
**Linked test spec:** [test-specification.md](test-specification.md)  
**Linked ADRs:** [ADR-0001](adr/0001-transcription-backend.md), [ADR-0002](adr/0002-concurrency-and-resource-model.md)

---

## Guiding principles

**Privacy is a constraint, not a feature.** Audio must be processed in-memory and never logged. This is an architecture decision made in Increment 1 and honored throughout — not a hardening pass added later.

**Working product as early as possible.** Increment 1 alone produces a demonstrable, evaluable service. Each subsequent increment extends it without breaking what exists.

**Ordering logic:** core pipeline → speaker attribution → format breadth → edge-case safety → load capacity → streaming.

---

## Increment overview

| # | Name | Goal after this increment | Tests first unlocked |
|---|---|---|---|
| 1 | Foundation | WAV → timestamped transcript, privacy-safe by design, upload limits | TC-101 to TC-106, TC-201, TC-203, TC-205, TC-501 to TC-504, TC-711, TC-712 |
| 2 | Speaker diarisation | Each segment carries an accurate speaker label | TC-202, TC-204, TC-303 to TC-306 |
| 3 | Multi-format input | Accepts WAV, MP3, FLAC, M4A, OGG, WebM, MP4 | TC-401 to TC-407, TC-705 to TC-706 |
| 4 | Robustness | No 5xx on any input; all edge cases handled | TC-102 to TC-104, TC-701 to TC-710 |
| 5 | Performance | Meets RTF targets; handles concurrent load | TC-601 to TC-604, TC-713 |
| 6 | Streaming *(extra credit)* | SSE or WebSocket endpoint yields segments in real time | TC-801 to TC-803 |

---

## Increment 1 — Foundation

**Goal:** A deployable service that accepts a WAV file and returns a structured JSON transcript with per-segment timestamps, language detection, and audio duration — with privacy guaranteed by design. No diarisation yet; speaker field absent or null.

**Shippable state after this increment:** evaluators can run the service, POST a WAV file, and receive a machine-readable transcript. All TC-1xx and TC-2xx (partial) pass.

---

### US-01 — Project skeleton

*As a developer, I want a reproducible project setup, so that onboarding and deployment are predictable.*

- `pyproject.toml` (or `requirements.txt`) pins all dependencies with exact versions
- `docker-compose.yml` (or equivalent) starts the service with a single command
- Service starts without error; process exits cleanly on SIGTERM
- README documents: install, run locally, run with Docker, example `curl` request

*No tests directly — enables all others.*

---

### US-02 — Health check endpoint

*As an operator, I want `GET /health` to report whether models are loaded, so that I can gate traffic until the service is ready.*

- Returns `200 OK` with `{"status": "ok", "models_loaded": true}` once the **faster-whisper** model is loaded (pyannote does not exist yet in Increment 1; US-06 extends this check to include it)
- Returns `{"status": "starting", "models_loaded": false}` (or `503`) while the model is still loading
- The model is loaded once at startup, not on the first request

*Contributes to TC-601 (model preload prerequisite).*

---

### US-03 — Accept WAV, return transcript with timestamps

*As an API consumer, I want to POST a WAV audio file and receive a JSON transcript, so that I can display the spoken content.*

- `POST /transcribe` accepts `multipart/form-data` with field `file` containing a WAV file
- Returns `200` with `Content-Type: application/json`
- Response body is valid JSON containing a `segments` array
- Each segment contains `start` (float, seconds), `end` (float, seconds), `text` (string)
- `start < end` for every segment; segments sorted ascending by `start`
- No segment `end` exceeds audio `duration` by more than 0.5 s
- faster-whisper `large-v3` model used for transcription (per ADR-0001)

*Tests: TC-101, TC-105, TC-106, TC-202 (partial), TC-203.*

---

### US-04 — Include language and duration in response

*As an API consumer, I want the response to include the detected language code and total audio duration, so that I can display or validate them without re-inspecting the file.*

- Response contains `language` (string, ISO 639-1 code, e.g. `"de"`)
- Response contains `duration` (float, seconds)
- `language` reflects faster-whisper's detected language, not a hardcoded value

*Tests: TC-201.*

---

### US-05 — Audio processed in memory; no content in logs

*As a user, I want confidence that my audio and transcript are never persisted or logged, so that sensitive recordings stay private.*

- Audio bytes are held in memory (`io.BytesIO` or equivalent); no explicit write to disk during WAV processing
- Structured logger never emits audio bytes, file contents, or transcript text at any log level
- After the response is sent, no files containing audio data exist in `/tmp`, the working directory, or any configured temp path
- Transcript text is not written to any log sink after the response is sent

*Tests: TC-501, TC-502, TC-503, TC-504.*

---

### US-23 — Enforce upload size and duration limits

*As an operator, I want oversized or over-long uploads rejected early, so that a single request cannot exhaust service memory or violate the privacy constraint during decode.*

> Added in the v1.1 architectural review (FINDINGS R-06). Placed in Increment 1 because it is a cheap guardrail that protects every later increment — see [ADR-0002](adr/0002-concurrency-and-resource-model.md) §3.

- Uploads exceeding `MAX_UPLOAD_BYTES` (default 100 MB) are rejected with `413` while streaming the body — the full payload is never buffered to measure it
- Audio whose probed duration exceeds `MAX_AUDIO_DURATION_S` (default 7200 s) is rejected with `422` after a metadata probe, before full decode
- Both limits are configurable via environment variables with safe defaults
- Error responses use the canonical envelope (`code: "file_too_large"` / `"audio_too_long"`)

*Tests: TC-711, TC-712.*

---

## Increment 2 — Speaker Diarisation

**Goal:** Every segment in the response carries a consistent speaker label. A 2-speaker recording produces exactly 2 distinct labels with DER ≤ 20%.

**Shippable state:** all core requirements (REQ-CORE-1 through REQ-CORE-3) satisfied. Evaluators can verify accuracy, timestamps, and speaker attribution.

**Prerequisite:** pyannote model license accepted once on HuggingFace, and `HF_TOKEN` available **at image build time** to fetch the gated weights (per ADR-0001 model-sourcing strategy). The token is *not* needed in the running container — weights are baked into the image and loaded offline.

---

### US-06 — Integrate pyannote diarisation

*As an API consumer, I want each transcript segment to include a speaker label, so that I can attribute speech to specific individuals.*

- pyannote `speaker-diarization-3.1` pipeline loaded at startup alongside faster-whisper
- pyannote weights are available offline at runtime (baked into the image at build time per ADR-0001 model-sourcing strategy); the service does not download them on first request
- Each segment in the response contains `speaker` (string, e.g. `"SPEAKER_00"`)
- All speaker values across a response use a consistent label set (no spelling drift)
- A single-speaker recording produces exactly one distinct `speaker` value
- A 2-speaker recording produces exactly two distinct `speaker` values
- The `GET /health` check from US-02 is extended to also report pyannote readiness; `models_loaded` is true only once **both** models are loaded

*Tests: TC-202 (full), TC-204, TC-304, TC-305.*

---

### US-07 — Align speaker turns with transcription segments

*As an API consumer, I want speaker labels to match the timing of each transcript segment, so that attribution is spatially accurate.*

- For each faster-whisper segment, the dominant pyannote speaker within `[start, end]` is assigned as the segment's speaker
- DER ≤ 20 % measured against `clear_de_2spk_30s.ground_truth.json`
- Segment boundaries are not altered by the alignment step; only `speaker` is added

*Tests: TC-303.*

---

## Increment 3 — Multi-Format Input

**Goal:** The service accepts any common audio format a browser, mobile device, or audio workstation might produce. Unsupported types return a clear 4xx.

**Shippable state:** TC-4xx pass. Service usable without client-side format conversion.

---

### US-08 — Decode audio from bytes regardless of container

*As an API consumer, I want the service to detect the audio format from the file content (not the filename extension), so that I can upload files without renaming them.*

- Format detection uses magic bytes / libav probe, not the `filename` or `Content-Type` header provided by the client
- Detected format is decoded **and resampled to 16 kHz mono int16 PCM** — the format faster-whisper expects. Browser-recorded WebM/Opus is typically 48 kHz stereo, so downmix + resample is mandatory, not optional. The resampling path (ffmpeg/libav) is fixed and documented so accuracy is reproducible across formats
- If conversion requires a temporary file (e.g. ffmpeg intermediary), that file is deleted before the response is returned — audio must not persist on disk beyond the request lifecycle (per ADR-0001)

*Contributes to TC-501 (privacy); prerequisite for US-09.*

---

### US-09 — Support MP3, FLAC, M4A, OGG, WebM, and MP4

*As an API consumer, I want to upload files in MP3, FLAC, M4A, OGG, WebM/Opus, and MP4 format, so that I am not forced to convert before uploading.*

- Each format listed in TC-401 through TC-407 returns `200` with a non-empty `segments` array
- Transcript WER against the WAV baseline for the same content is ≤ 20% (allowing for codec-introduced distortion)
- Format variants (`same_audio.*`) produce equivalent transcripts to `clear_en_1spk_10s.wav`

*Tests: TC-402, TC-403, TC-404, TC-405, TC-406, TC-407.*

---

### US-10 — Reject non-audio files with a descriptive error

*As an API consumer, I want a 4xx response with a machine-readable error when I upload a non-audio file, so that my client can surface a useful message.*

- A file with a PDF magic header (regardless of extension) returns `415` or `422`
- A file with a `.wav` extension but non-audio content returns `415` or `422`
- Response body is valid JSON with an `error` key containing a human-readable description
- Service does not return `500` and does not crash

*Tests: TC-705, TC-706.*

---

## Increment 4 — Robustness

**Goal:** The service returns no `5xx` on any input, recovers cleanly from client disconnects, and handles all semantic edge cases described in the test spec.

**Shippable state:** TC-7xx pass. Service is production-safe under adversarial or unexpected input.

**Parallelisable:** US-11 through US-17 have no dependencies on each other and can be assigned to different developers simultaneously. US-17 (disconnect handling) is the most involved — see ADR-0002 §4 before starting it.

---

### US-11 — Validate request structure at the HTTP layer

*As an API consumer, I want a `400` or `422` when I omit the file field or send the wrong Content-Type, so that API misuse fails fast with a useful message.*

- `POST /transcribe` with no `file` field → `400` with JSON `error` body
- `POST /transcribe` with field named anything other than `file` → `400` or `422`
- `POST /transcribe` with `Content-Type: application/json` → `400` or `415`
- All error responses are valid JSON

*Tests: TC-102, TC-103, TC-104.*

---

### US-12 — Reject empty files

*As an API consumer, I want a `400` error for zero-byte files, not a crash, so that empty uploads fail fast.*

- A zero-byte file returns `400` with JSON `error` body
- Service remains alive after the request

*Tests: TC-707.*

---

### US-13 — Return empty transcript for silence

*As an API consumer, I want silence-only audio to return `200` with an empty `segments` array, so that my client does not need to special-case error codes for silent recordings.*

- `silence_10s.wav` returns `200` with `"segments": []`
- No `500` or unhandled exception

*Tests: TC-701.*

---

### US-14 — Return best-effort transcript for noisy audio; reject corrupt files cleanly

*As an API consumer, I want noisy audio to return a best-effort response and corrupt audio to return a `4xx`, so that neither causes a `500`.*

- `noisy_speech_30s.wav` → `200` with valid JSON (segments may be empty or partial)
- `corrupt.wav` (valid header, garbage payload) → `4xx` or `200` with empty segments; never `500`
- Service process remains alive after both requests

*Tests: TC-702, TC-708.*

---

### US-15 — Handle very short audio gracefully

*As an API consumer, I want audio clips shorter than 500 ms to return `200` with empty or minimal segments, so that edge-length clips do not crash the pipeline.*

- `very_short_200ms.wav` returns `200`; `segments` is an empty array or contains at most one entry
- No `500`

*Tests: TC-704.*

---

### US-16 — Process very long recordings without OOM

*As an API consumer, I want multi-hour recordings to complete eventually without crashing the service, so that batch transcription of long meetings is possible.*

- `long_90min.mp3` (90 min) returns `200` within a 2-hour client timeout
- Per-request memory is bounded by bounding worker concurrency, not by holding many full files at once ([ADR-0002](adr/0002-concurrency-and-resource-model.md) §3): a 90-min file decodes to ~172 MB PCM, and only N (worker count) such buffers are resident simultaneously
- "In-memory" (US-05) means *not persisted to disk*, not *entire file resident with unbounded copies* — this resolves the apparent tension between US-05, US-16, and US-19 flagged in the review (R-02)
- No `500`; service remains alive after the request

*Tests: TC-703.*

---

### US-17 — Survive client disconnect without resource leak

*As an operator, I want the service to clean up processing state when a client disconnects mid-request, so that abandoned requests do not leak memory, handles, or temp files.*

- Client connects, sends `long_90min.mp3`, closes TCP after 5 s
- A subsequent valid request from a different client returns `200` with a correct transcript
- No orphaned threads, open file descriptors, or temp audio files remain after disconnect is detected
- Cancellation follows the [ADR-0002](adr/0002-concurrency-and-resource-model.md) §4 policy: the transcription segment-generator loop checks `request.is_disconnected()` between segments and stops (freeing the worker within ~one segment); an in-flight pyannote call cannot be interrupted mid-call but its result is discarded and the slot released immediately after; a hard `REQUEST_TIMEOUT_S` bounds worst-case occupancy
- This story's design depends on ADR-0002 §4 — read it before implementing, since "just run it in an executor" does **not** cancel on disconnect (R-03)

*Tests: TC-710.*

---

## Increment 5 — Performance

**Goal:** Single-request latency meets the RTF target for the deployment hardware. Ten concurrent requests complete without errors. Memory stays flat across 20 sequential requests.

**Shippable state:** TC-6xx pass. Service is production-ready under real load.

---

### US-18 — Meet single-request latency target

*As an API consumer, I want a 30 s audio file transcribed within the hardware-appropriate RTF target, so that the service is usable in a real-time workflow.*

- Median latency over 5 runs with `clear_de_2spk_30s.wav`:
  - GPU deployment: ≤ 15 s (RTF 0.5)
  - CPU int8 deployment: ≤ 60 s (RTF 2.0)
- RTF is measured **end-to-end** (decode + resample + transcription + diarisation + serialisation), not transcription-only — per [ADR-0002](adr/0002-concurrency-and-resource-model.md) §5
- Hardware profile (CPU/GPU model, quantisation setting) recorded in test report

*Tests: TC-601.*

---

### US-19 — Handle concurrent requests without errors

*As an API consumer, I want 10 simultaneous requests to complete successfully, so that the service is usable under real user load.*

- Concurrency follows the [ADR-0002](adr/0002-concurrency-and-resource-model.md) §1 model: N worker processes, each owning **private** faster-whisper and pyannote instances (no model shared across threads — resolves the pyannote thread-safety risk); inference serialised per worker by a bounded semaphore
- 10 simultaneous `POST /transcribe` requests with `clear_de_2spk_30s.wav` all return `200`
- No request hangs indefinitely
- p95 latency across 10 concurrent requests ≤ 3 × single-request baseline p95, measured at a **documented worker count** (ADR-0002 §1)
- Requests beyond the configured `QUEUE_DEPTH` are shed with `503` + `Retry-After`, not OOM (ADR-0002 §2)

*Tests: TC-602, TC-603, TC-713.*

---

### US-20 — Memory stays flat across sequential requests

*As an operator, I want RSS memory to remain stable after 20 sequential requests, so that I don't need to schedule service restarts.*

- RSS after request 20 does not exceed RSS after request 1 by more than 50 MB (model weight baseline excluded; only incremental growth counted)
- Measured with `clear_en_1spk_10s.wav` to isolate per-request allocation

*Tests: TC-604.*

---

## Increment 6 — Streaming *(extra credit)*

**Goal:** A second endpoint emits transcript segments in real time as audio is processed, enabling live caption display without waiting for the full file to be processed.

**Shippable state:** TC-8xx pass. Frontend can display captions as a recording is uploaded.

---

### US-21 — Stream transcript segments via SSE or WebSocket

*As an API consumer, I want to receive transcript segments as they are produced, not after the full file is processed, so that I can display captions in near-real time.*

- A streaming endpoint (WebSocket or SSE) exists and accepts audio data
- At least one segment event is emitted before the full audio duration elapses (RTF < 1 on GPU)
- Each event carries the same `{start, end, text, speaker}` schema as the batch endpoint
- Connection is accepted without `404` or `501`

*Tests: TC-801, TC-802.*

---

### US-22 — Server cleans up on stream client disconnect

*As an operator, I want streaming connections to release all resources when a client disconnects, so that abandoned streams do not accumulate.*

- Client connects to streaming endpoint, begins sending audio, disconnects after 3 s
- No orphaned threads or open audio file handles remain 10 s after disconnect
- Service remains responsive to new requests

*Tests: TC-803.*

---

## Requirement traceability

| Requirement | Increment | User stories |
|---|---|---|
| REQ-CORE-1: Accept audio, return transcript | 1 | US-03 |
| REQ-CORE-2: Timestamps | 1 | US-03, US-04 |
| REQ-CORE-3: Speaker diarisation | 2 | US-06, US-07 |
| REQ-CORE-4: Common audio formats | 3 | US-08, US-09 |
| REQ-PRIV-1/2/3: No retention, no logging | 1 (by design) | US-05, US-08 |
| REQ-PERF-1: Reasonable latency | 5 | US-02, US-18 |
| REQ-PERF-2: Concurrent requests | 5 | US-19, US-17 |
| REQ-QUAL-1: Accuracy | 1+2 | US-03, US-07 |
| REQ-QUAL-2: Graceful edge cases | 1+4 | US-11–US-17, US-23 |
| REQ-QUAL-3: Structured response | 1 | US-03, US-04 |
| ADR-0002: Resource ceilings & backpressure | 1+5 | US-23, US-19 |
| EXTRA: Streaming | 6 | US-21, US-22 |

---

## Execution notes

**Do not defer privacy.** US-05 is part of Increment 1. If the architecture is correct from the start (in-memory processing, structured logging without content), TC-5xx will pass without a separate hardening pass.

**README grows with each increment.** Start with setup + basic `curl` in Increment 1. Add format examples in Increment 3, concurrent load instructions in Increment 5, streaming examples in Increment 6.

**HuggingFace prerequisite blocks Increment 2.** Obtain `HF_TOKEN` and accept the pyannote model license before starting Increment 2. This is an out-of-band step with no code dependency.

**Increment 4 stories are mostly independent.** US-11 through US-17 do not depend on each other and can be worked in parallel.

**Hardware must be documented.** TC-601 results are meaningless without recording CPU/GPU model and quantisation setting (`int8` / `float16` / `float32`).
