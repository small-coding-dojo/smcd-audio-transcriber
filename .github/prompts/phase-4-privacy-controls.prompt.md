---
description: "Implement Phase 4 (Privacy / No-Persistence Controls) of the Audio Transcriber Service"
name: "Phase 4: Privacy / No-Persistence Controls"
agent: "agent"
---
Read [PROJECT_BRIEF.md](../../PROJECT_BRIEF.md) and the high-level plan in [plan-audioTranscriberService.prompt.md](./plan-audioTranscriberService.prompt.md) for full context. This phase is cross-cutting but is verified as its own hardening pass after [Phase 3](./phase-3-api-layer.prompt.md) is complete.

Implement **Phase 4: Privacy / No-Persistence Controls**.

**Tasks:**
- Audit and enforce: no audio bytes are ever written to disk. Use `tempfile` with `delete=True`/in-memory buffers only, except where an ML library forces disk I/O (e.g., `ffmpeg` or `torchaudio` needing a file path). Wrap all temp file usage in guaranteed cleanup (`try`/`finally`, context managers), including on exceptions and client disconnects.
- Audit and enforce: no logging middleware or library logs request bodies, file contents, or transcript text. Add a lint/test step (e.g., a grep-based check or a log-capture test) to catch accidental logging of payloads.
- Verify that the inference libraries (`faster-whisper`, `whisperx`, `pyannote`) do not cache the specific uploaded audio anywhere persistent; redirect any intermediate files they write to an ephemeral tmpfs/temp dir that is cleaned per-request.
- Document the data flow in the README: audio is in memory/temp only, the transcript is returned once and never stored server-side, and there is no analytics/telemetry capturing content.
- Flag the open question: whether an in-memory tmpfs (RAM-backed temp dir) is required/available in the deployment environment, or whether a standard OS temp dir with immediate deletion is acceptable (see open question 6 in the master plan).

**Definition of done:**
- A test (manual or automated) confirms no temp files remain on disk after a request completes or fails.
- A log-capture test confirms transcript text and audio content never appear in logs.
- The README documents the no-persistence data flow guarantees.
