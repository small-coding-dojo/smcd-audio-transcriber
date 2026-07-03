## Plan: ClearVoice Audio Transcriber Service - High-Level Implementation Plan

TL;DR: Build a Python + FastAPI service exposing a single upload endpoint that transcribes audio using a locally-hosted Whisper model (via faster-whisper for speed) and performs diarisation via WhisperX (Whisper + forced alignment + pyannote-based speaker labelling). Everything runs in-memory / temp-only to satisfy strict no-persistence privacy rules. Concurrency is handled via async request handling plus a bounded worker pool/queue to protect CPU/GPU resources. Real-time streaming (WebSocket/SSE) is a stretch phase after the batch endpoint is solid.

**Decisions (confirmed with user)**
- Language/framework: Python + FastAPI.
- Transcription engine: local model, not cloud API (avoids sending audio to third parties, satisfies privacy requirement more directly). Likely `faster-whisper` (CTranslate2-based) for better latency/throughput than vanilla `openai-whisper`.
- Diarisation: WhisperX (bundles transcription, word-level alignment, and pyannote.audio-based diarisation, and speaker-label attachment to segments).
- Real-time/streaming extra credit: included as a final stretch phase, after the core batch service is complete and hardened.

---

### Phase 0: Scaffolding & Project Setup
- Initialize Python project (pyproject.toml/poetry or requirements.txt + venv), repo structure (`app/`, `tests/`, `README.md`).
- Set up FastAPI app skeleton, health-check endpoint, config module (env vars for model size, device, concurrency limits, max upload size/duration).
- Set up dependency management for heavy ML deps (faster-whisper, whisperx, pyannote.audio, torch/torchaudio, ffmpeg-python or subprocess ffmpeg).
- Decide and document model download/caching strategy at container build time vs first-run (models should be pre-baked into image/container to avoid runtime network calls, which also helps the "no external calls with audio data" privacy story).
- Set up structured logging with a strict rule: log only metadata (request id, duration, status, file size/duration), never audio content, transcript text, or file paths containing user data.
- Open question: Docker vs bare-metal deployment target; GPU vs CPU-only assumption (affects model size choice and latency expectations).

### Phase 1: Core Transcription Pipeline (Batch, Single Speaker Assumption First)
- Implement audio ingestion: accept upload, validate content-type/extension, convert to a normalized format (e.g., 16kHz mono WAV) via ffmpeg entirely in-memory or to a securely-handled temp file that is deleted immediately after processing (even on error paths - use try/finally).
- Integrate faster-whisper for transcription, producing segments with start/end timestamps and text.
- Define internal transcript data model (segments list: start, end, text, speaker placeholder) and the API response schema.
- Handle basic format/duration validation and reject unsupported formats early with clear error responses.
- Technical decisions to flag: which Whisper model size (tiny/base/small/medium/large-v3) as default, trade-off of accuracy vs latency; whether to auto-detect language or assume English.

### Phase 2: Speaker Diarisation
- Integrate WhisperX pipeline: transcription + forced alignment (word-level timestamps) + pyannote diarisation, then merge diarisation output with transcript segments to produce speaker-labelled segments (Speaker 1, Speaker 2, ...).
- Handle diarisation-specific requirements: pyannote.audio typically requires a HuggingFace auth token for pretrained pipelines - decide how this is provisioned securely (env var/secret, not committed) - flag as open question/config item.
- Handle edge case: single-speaker audio (diarisation should not fabricate multiple speakers) and diarisation failures (fallback to un-labelled transcript rather than failing the whole request).
- Technical decision: run diarisation always vs make it optional per-request (adds latency); default recommendation is always-on since it's a core requirement, but expose as a toggle for latency-sensitive callers - flag as open question.

### Phase 3: API Layer & Response Contract
- Finalize single endpoint: e.g., `POST /transcribe` (multipart/form-data file upload), synchronous response with full structured JSON (segments with start/end/speaker/text, plus top-level metadata: duration, detected language, processing time).
- Input validation: max file size/duration limits (configurable), accepted MIME types/extensions, meaningful 4xx errors for invalid input, 413 for oversized files.
- Error handling contract: consistent error schema (code, message) for all failure modes (bad format, corrupt file, silence-only, timeout, internal error) - never leak stack traces or file paths.
- Technical decision: synchronous request/response vs async job (submit + poll) for long recordings - brief implies a single endpoint returning the transcript, so default to synchronous with a sane max-duration cap and document that longer files should be chunked/queued in future - flag as open question if very long recordings must be supported without blocking.

### Phase 4: Privacy / No-Persistence Controls (Cross-Cutting, but Verified as Own Phase)
- Audit and enforce: no audio bytes ever written to disk (use `tempfile` with `delete=True`/in-memory buffers only where the ML libraries force disk I/O, e.g., ffmpeg or torchaudio needing a file path); wrap all temp file usage in guaranteed cleanup (`try/finally`, context managers) including on exceptions and client disconnects.
- Audit and enforce: no logging middleware or library logs request bodies, file contents, or transcript text; add a lint/test step (e.g., grep-based check or log-capture test) to catch accidental logging of payloads.
- Ensure model inference libraries (faster-whisper, whisperx, pyannote) don't cache the specific uploaded audio anywhere persistent (some libraries write intermediate files - verify and redirect to ephemeral tmpfs/temp dirs that are cleaned per-request).
- Document data flow in README: audio in memory/temp only, transcript returned once and never stored server-side, no analytics/telemetry capturing content.
- Open question: is an in-memory tmpfs (RAM-backed temp dir) required/available in the deployment environment, or is a standard OS temp dir with immediate deletion acceptable?

### Phase 5: Performance, Concurrency & Resource Management
- Run CPU/GPU-bound transcription+diarisation work in a bounded worker pool (e.g., `ProcessPoolExecutor` or a task queue) so FastAPI's event loop isn't blocked and concurrent requests are throttled rather than causing resource exhaustion.
- Add configurable concurrency limit (max simultaneous inference jobs) with queueing/backpressure (e.g., 429/503 with retry-after when saturated) rather than unbounded thread/process spawning.
- Consider model instance reuse (load model once at startup, share across requests) instead of reloading per request, given memory footprint of Whisper/pyannote models.
- Load/perf testing plan: single large file latency benchmark, concurrent-request benchmark (e.g., locust/k6), memory/CPU profiling under load.
- Technical decision: single shared model instance (thread-safety/serialization needed) vs a small pool of model instances - trade-off between memory usage and throughput - flag as open question, depends on target hardware.

### Phase 6: Edge Cases & Graceful Error Handling
- Silence-only audio: detect low-energy/no-speech segments (Whisper's no-speech probability or a VAD pre-pass) and return a valid empty-transcript response rather than an error or nonsense text.
- Background noise: rely on Whisper's inherent robustness; consider optional VAD pre-filtering to trim leading/trailing silence and reduce hallucination on noisy segments.
- Very long recordings: enforce a configurable max duration/file size; return a clear 4xx if exceeded; document chunked/async processing as a future enhancement if long files must be supported.
- Unsupported/corrupt formats: validate via ffprobe/ffmpeg before full processing; return descriptive 4xx errors distinguishing "unsupported format" from "corrupt/unreadable file".
- Timeouts: define per-request processing timeout with clean cancellation and temp-file cleanup.

### Phase 7: Testing
- Unit tests: audio validation logic, response schema construction, error mapping, config parsing.
- Integration tests: end-to-end transcription against small fixture audio clips (short speech, silence, multi-speaker sample, unsupported format, oversized file) - use short synthetic/public-domain clips checked into `tests/fixtures/`.
- Privacy tests: assert no temp files remain after request completion/failure; assert logs (captured via test harness) never contain transcript text or filenames with content.
- Concurrency/load tests: scripted concurrent requests to validate throttling behavior and stable memory usage (can be a lighter-weight smoke version of Phase 5's full load test).
- Technical decision: mock the ML models in most unit/integration tests (for speed) but keep a small "real model" smoke test suite behind a slower test marker.

### Phase 8: Documentation & Deliverables
- README: build/run instructions (Docker preferred for reproducible ffmpeg/torch/model deps), configuration reference (env vars), API contract/example request-response, privacy notes, known limitations.
- Document model choice rationale, hardware requirements/recommendations (CPU vs GPU), and how to swap model size.
- Document testing instructions (how to run unit vs integration vs load tests).

### Phase 9 (Stretch): Real-Time Streaming Extra Credit
- Add a WebSocket (or SSE) endpoint accepting a live microphone audio stream.
- Chunk incoming audio into rolling windows, run incremental transcription (faster-whisper supports partial/streaming-style usage; diarisation is harder to do incrementally - likely deferred or done on rolling buffer with re-labelling).
- Return incremental transcript segments to the client as they become available; final flush/finalize on stream close.
- Same privacy rules apply: no persistence of streamed audio or partial transcripts beyond the live connection.
- Open question: is true low-latency streaming diarisation in scope, or is "streaming transcription, diarisation only on finalize" an acceptable reduced scope for the stretch goal?

---

**Requirement coverage checklist**
- File upload endpoint -> Phase 3.
- Timestamps -> Phase 1 (segment start/end from Whisper).
- Speaker diarisation -> Phase 2.
- Format support -> Phase 1 ingestion/normalization + Phase 6 validation.
- No-storage/no-logging of audio and transcripts -> Phase 4 (dedicated).
- Latency -> Phase 5 (model choice, worker pool) + Phase 7 (benchmarks).
- Concurrency -> Phase 5.
- Graceful error handling (silence, noise, long recordings, unsupported formats) -> Phase 6.

**Open questions / assumptions to clarify before detailed design**
1. Deployment target and hardware: Docker container? GPU available or CPU-only? This drives Whisper model size default and expected latency.
2. Max supported audio duration/file size - brief says "very long recordings" must be handled gracefully, but doesn't define a limit; need a concrete cap for synchronous processing.
3. pyannote.audio HuggingFace token provisioning for diarisation pipeline - how is this secret supplied in each environment (local dev, CI, prod)?
4. Language scope - English-only or multi-language auto-detect (affects model config and testing fixtures).
5. Synchronous vs async job model for the endpoint - assumed synchronous single-call per brief wording, but worth confirming given "very long recordings" edge case.
6. Whether an in-memory/tmpfs temp directory is available in target deployment for stricter no-disk-write guarantees, or standard temp-dir-with-immediate-delete is acceptable.
7. Whether real-time diarisation is truly required for the stretch goal, or reduced scope (streaming transcription + diarisation only at stream end) is acceptable.
