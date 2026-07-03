---
description: "Implement Phase 2 (Speaker Diarisation) of the Audio Transcriber Service"
name: "Phase 2: Speaker Diarisation"
agent: "agent"
---
Read [PROJECT_BRIEF.md](../../PROJECT_BRIEF.md) and the high-level plan in [plan-audioTranscriberService.prompt.md](./plan-audioTranscriberService.prompt.md) for full context. This phase builds on [Phase 1](./phase-1-core-transcription.prompt.md), which must be completed first.

Implement **Phase 2: Speaker Diarisation**.

**Tasks:**
- Integrate the WhisperX pipeline: transcription + forced alignment (word-level timestamps) + pyannote diarisation, then merge the diarisation output with the transcript segments produced in Phase 1 to produce speaker-labelled segments (`Speaker 1`, `Speaker 2`, ...).
- Handle the pyannote.audio HuggingFace auth token requirement: provision it securely via an environment variable/secret, never commit it, and document how it must be supplied in local dev, CI, and production (see open question 3 in the master plan).
- Handle the single-speaker edge case: diarisation must not fabricate multiple speakers when only one speaker is present.
- Handle diarisation failures gracefully: fall back to an un-labelled transcript rather than failing the whole request.
- Decide whether diarisation runs always vs is optional per-request (it adds latency). Default recommendation: always-on, since it is a core requirement, but expose a toggle for latency-sensitive callers. Document this decision.

**Definition of done:**
- Transcript segments include speaker labels when multiple speakers are detected, and no fabricated labels for single-speaker audio.
- A diarisation failure degrades gracefully to an un-labelled transcript instead of an error response.
- The HuggingFace token provisioning approach is documented.
- The always-on-vs-optional diarisation decision is documented (and implemented as a config toggle if made optional).
