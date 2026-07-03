---
description: "Generate a rough implementation plan for the Audio Transcriber Service from the project brief"
name: "Plan Implementation"
agent: "plan"
---
Read [PROJECT_BRIEF.md](../../PROJECT_BRIEF.md) and produce a rough, high-level implementation plan for the Audio Transcriber Service.

The plan should:
- Break the work into ordered phases/milestones (e.g., project scaffolding, core transcription pipeline, diarisation, API layer, privacy/no-persistence controls, performance/concurrency handling, testing, docs).
- For each phase, list the key tasks and call out major technical decisions that need to be made (e.g., transcription engine/model choice, diarisation approach, streaming vs batch processing, framework/language choice).
- Explicitly address each requirement from the brief: file upload endpoint, timestamps, speaker diarisation, format support, no-storage/no-logging of audio and transcripts, latency, concurrency, graceful error handling for edge cases (silence, noise, long recordings, unsupported formats).
- Flag open questions or assumptions that would need clarification before detailed design.
- Keep it high-level (a rough plan, not a full task breakdown) — bullet points over prose.
- Do not write or modify any code or files; only output the plan as a chat response.