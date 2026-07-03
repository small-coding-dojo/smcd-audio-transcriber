---
description: "Implement Phase 6 (Edge Cases & Graceful Error Handling) of the Audio Transcriber Service"
name: "Phase 6: Edge Cases & Graceful Error Handling"
agent: "agent"
---
Read [PROJECT_BRIEF.md](../../PROJECT_BRIEF.md) and the high-level plan in [plan-audioTranscriberService.prompt.md](./plan-audioTranscriberService.prompt.md) for full context. This phase builds on [Phase 5](./phase-5-performance-concurrency.prompt.md), which must be completed first.

Implement **Phase 6: Edge Cases & Graceful Error Handling**.

**Tasks:**
- Silence-only audio: detect low-energy/no-speech segments (using Whisper's no-speech probability or a VAD pre-pass) and return a valid empty-transcript response rather than an error or nonsense text.
- Background noise: rely on Whisper's inherent robustness; add optional VAD pre-filtering to trim leading/trailing silence and reduce hallucination on noisy segments.
- Very long recordings: enforce the configurable max duration/file size from Phase 0/3 config, and return a clear 4xx if exceeded; document chunked/async processing as a future enhancement if long files must be supported.
- Unsupported/corrupt formats: validate via `ffprobe`/`ffmpeg` before full processing, and return descriptive 4xx errors that distinguish "unsupported format" from "corrupt/unreadable file".
- Timeouts: define a per-request processing timeout with clean cancellation and guaranteed temp-file cleanup (reusing the Phase 4 cleanup guarantees).

**Definition of done:**
- Silence-only audio returns a valid empty-transcript response, not an error.
- Oversized/overlong files return a clear 4xx (or 413) before full processing begins where possible.
- Corrupt or unsupported format files return descriptive, distinct 4xx errors.
- Long-running requests are cancelled cleanly after a configurable timeout, with temp files still cleaned up.
