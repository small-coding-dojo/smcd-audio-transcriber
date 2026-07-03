---
description: "Implement Phase 3 (API Layer & Response Contract) of the Audio Transcriber Service"
name: "Phase 3: API Layer & Response Contract"
agent: "agent"
---
Read [PROJECT_BRIEF.md](../../PROJECT_BRIEF.md) and the high-level plan in [plan-audioTranscriberService.prompt.md](./plan-audioTranscriberService.prompt.md) for full context. This phase builds on [Phase 2](./phase-2-diarisation.prompt.md), which must be completed first.

Implement **Phase 3: API Layer & Response Contract**.

**Tasks:**
- Finalize the single endpoint, e.g. `POST /transcribe` (multipart/form-data file upload), returning a synchronous response with full structured JSON: segments (`start`, `end`, `speaker`, `text`) plus top-level metadata (`duration`, `detected_language`, `processing_time`).
- Add input validation: max file size/duration limits (configurable via the Phase 0 config module), accepted MIME types/extensions, meaningful 4xx errors for invalid input, and 413 for oversized files.
- Define a consistent error schema (`code`, `message`) for all failure modes (bad format, corrupt file, silence-only, timeout, internal error). Never leak stack traces or file paths in responses.
- Decide synchronous request/response vs async job (submit + poll). The brief implies a single endpoint returning the transcript, so default to synchronous with a sane max-duration cap; document that longer files should be chunked/queued in a future iteration. Flag as an open question if very long recordings must be supported without blocking (see open question 5 in the master plan).

**Definition of done:**
- `POST /transcribe` accepts a file upload and returns the documented JSON response contract.
- All documented error cases return the consistent error schema with an appropriate HTTP status code.
- No stack traces, file paths, or internal details leak into error responses.
- The synchronous-vs-async decision is documented with rationale.
