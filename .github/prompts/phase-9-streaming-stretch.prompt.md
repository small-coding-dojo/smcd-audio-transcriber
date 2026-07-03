---
description: "Implement Phase 9 (Stretch: Real-Time Streaming Extra Credit) of the Audio Transcriber Service"
name: "Phase 9: Real-Time Streaming (Stretch)"
agent: "agent"
---
Read [PROJECT_BRIEF.md](../../PROJECT_BRIEF.md) and the high-level plan in [plan-audioTranscriberService.prompt.md](./plan-audioTranscriberService.prompt.md) for full context. This is a stretch phase that should only be started after [Phase 8](./phase-8-documentation.prompt.md) is complete and the core batch service is solid and hardened.

Implement **Phase 9 (Stretch): Real-Time Streaming Extra Credit**.

**Tasks:**
- Add a WebSocket (or SSE) endpoint accepting a live microphone audio stream.
- Chunk incoming audio into rolling windows and run incremental transcription (`faster-whisper` supports partial/streaming-style usage). Diarisation is harder to do incrementally, treat it as deferred, or run it on a rolling buffer with re-labelling.
- Return incremental transcript segments to the client as they become available, with a final flush/finalize when the stream closes.
- Apply the same privacy rules as the batch endpoint: no persistence of streamed audio or partial transcripts beyond the live connection (reuse the Phase 4 no-persistence guarantees).
- Decide and document the scope: true low-latency streaming diarisation vs "streaming transcription, diarisation only on finalize" as an acceptable reduced scope (see open question 7 in the master plan).

**Definition of done:**
- A WebSocket or SSE endpoint streams incremental transcript segments from a live audio stream.
- No streamed audio or partial transcript data persists beyond the connection's lifetime.
- The diarisation scope decision for streaming is documented.
- The README (Phase 8) is updated to describe the new streaming endpoint.
