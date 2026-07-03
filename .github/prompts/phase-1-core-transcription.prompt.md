---
description: "Implement Phase 1 (Core Transcription Pipeline) of the Audio Transcriber Service"
name: "Phase 1: Core Transcription Pipeline"
agent: "agent"
---
Read [PROJECT_BRIEF.md](../../PROJECT_BRIEF.md) and the high-level plan in [plan-audioTranscriberService.prompt.md](./plan-audioTranscriberService.prompt.md) for full context. This phase builds on the scaffolding from [Phase 0](./phase-0-scaffolding.prompt.md), which must be completed first.

Implement **Phase 1: Core Transcription Pipeline (Batch, Single Speaker Assumption First)**.

**Tasks:**
- Implement audio ingestion: accept an upload, validate content-type/extension, and convert it to a normalized format (e.g., 16kHz mono WAV) via `ffmpeg`. Do this entirely in-memory where possible, or via a securely-handled temp file that is deleted immediately after processing (use `try`/`finally` so cleanup happens even on error paths).
- Integrate `faster-whisper` for transcription, producing segments with start/end timestamps and text.
- Define the internal transcript data model (a list of segments, each with `start`, `end`, `text`, and a `speaker` placeholder field for the next phase) and the corresponding API response schema (e.g., Pydantic models).
- Add basic format/duration validation and reject unsupported formats early with clear error responses.
- Decide and document the default Whisper model size (tiny/base/small/medium/large-v3), weighing accuracy vs latency, and whether to auto-detect language or assume English (see open question 4 in the master plan).

**Definition of done:**
- An internal (not yet exposed via the final API contract, that is Phase 3) transcription function/service takes an audio upload and returns timestamped segments.
- Temp files, if used, are always cleaned up, including on exceptions.
- The default model size and language-detection behavior are documented with rationale.
- No speaker labels are produced yet, that is Phase 2.
