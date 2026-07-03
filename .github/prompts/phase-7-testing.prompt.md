---
description: "Implement Phase 7 (Testing) of the Audio Transcriber Service"
name: "Phase 7: Testing"
agent: "agent"
---
Read [PROJECT_BRIEF.md](../../PROJECT_BRIEF.md), the high-level plan in [plan-audioTranscriberService.prompt.md](./plan-audioTranscriberService.prompt.md), and the detailed test plan in [plan-tests.prompt.md](./plan-tests.prompt.md) (if it has already been run and its output captured) for full context. This phase builds on [Phase 6](./phase-6-edge-cases.prompt.md), which must be completed first.

Implement **Phase 7: Testing**.

**Tasks:**
- Unit tests: audio validation logic, response schema construction, error mapping, and config parsing.
- Integration tests: end-to-end transcription against small fixture audio clips (short speech, silence, multi-speaker sample, unsupported format, oversized file). Use short synthetic/public-domain clips checked into `tests/fixtures/`.
- Privacy tests: assert no temp files remain after request completion/failure; assert logs (captured via a test harness) never contain transcript text or filenames with content.
- Concurrency/load tests: scripted concurrent requests validating the throttling behavior and stable memory usage from Phase 5 (a lighter-weight smoke version of the full load test is sufficient here).
- Mock the ML models (`faster-whisper`, WhisperX/pyannote) in most unit/integration tests for speed, but keep a small "real model" smoke test suite behind a slower test marker (e.g., `pytest -m slow`).

**Constraints:**
- This phase only creates or modifies test files/test suites, never production/business logic code. If a bug is found in production code while writing tests, report it rather than silently fixing it outside this phase's scope.

**Definition of done:**
- Unit, integration, privacy, and concurrency/load test suites exist and pass.
- Fixture audio clips are checked into `tests/fixtures/`.
- Slow/real-model tests are clearly marked and excluded from the default fast test run.
