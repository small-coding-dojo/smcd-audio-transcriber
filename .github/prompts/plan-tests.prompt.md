---
description: "Generate a rough automated test plan for the Audio Transcriber Service, scoped strictly to testing (no business logic)"
name: "Plan Tests"
agent: "Plan"
---
Read [PROJECT_BRIEF.md](../../PROJECT_BRIEF.md) and the output of the [Plan Implementation](./plan-implementation.prompt.md) prompt (if available) and produce a rough, high-level plan for the automated test suite of the Audio Transcriber Service.

The plan should:
- Break testing into categories: unit tests (individual pipeline components, e.g., audio decoding, transcription, diarisation, timestamp alignment), integration tests (the HTTP endpoint end to end), edge case tests (silence, background noise, very long recordings, unsupported/corrupted formats, empty uploads), concurrency/load tests (multiple simultaneous requests), privacy/compliance tests (assert no audio is written to disk, no audio or transcript content is logged, nothing persists after the response is sent), and performance/latency tests (response time relative to audio length).
- For each category, list the key test cases and note what should be mocked or stubbed (e.g., the transcription/diarisation engine) versus tested against real audio samples.
- Recommend suitable test tooling/frameworks once the implementation language/framework is known, or list options per likely stack if not yet decided.
- Flag open questions or assumptions (e.g., availability of sample audio fixtures, need for synthetic/generated audio for edge cases).
- Keep it high-level (a rough plan, not full test code) — bullet points over prose.

Constraints:
- This prompt is for planning only; do not write or modify any code or files, only output the plan as a chat response.
- The plan must never include or suggest implementing business logic (transcription, diarisation, API handlers, etc.) — scope is strictly test planning and, if later executed, strictly test code.
- If this plan is later handed to an implementation task, that task must only create or modify test files/test suites, never production/business logic code.