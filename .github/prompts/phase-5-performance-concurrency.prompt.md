---
description: "Implement Phase 5 (Performance, Concurrency & Resource Management) of the Audio Transcriber Service"
name: "Phase 5: Performance, Concurrency & Resource Management"
agent: "agent"
---
Read [PROJECT_BRIEF.md](../../PROJECT_BRIEF.md) and the high-level plan in [plan-audioTranscriberService.prompt.md](./plan-audioTranscriberService.prompt.md) for full context. This phase builds on [Phase 4](./phase-4-privacy-controls.prompt.md), which must be completed first.

Implement **Phase 5: Performance, Concurrency & Resource Management**.

**Tasks:**
- Run the CPU/GPU-bound transcription and diarisation work in a bounded worker pool (e.g., `ProcessPoolExecutor` or a task queue) so FastAPI's event loop is not blocked and concurrent requests are throttled rather than causing resource exhaustion.
- Add a configurable concurrency limit (max simultaneous inference jobs) with queueing/backpressure (e.g., return 429/503 with `Retry-After` when saturated) instead of unbounded thread/process spawning.
- Load the model instance(s) once at startup and share/reuse them across requests instead of reloading per request, given the memory footprint of Whisper/pyannote models.
- Decide between a single shared model instance (requiring thread-safety/serialization) vs a small pool of model instances, trading off memory usage against throughput. Document this decision (depends on target hardware, see open question 1 in the master plan).
- Write a load/perf testing plan and, where practical, execute it: single large-file latency benchmark, concurrent-request benchmark (e.g., `locust` or `k6`), and memory/CPU profiling under load.

**Definition of done:**
- Inference work runs off the main event loop via a bounded worker pool/queue.
- A configurable concurrency limit is enforced with graceful 429/503 backpressure responses when exceeded.
- Models are loaded once at startup, not per request.
- Benchmark results (or a documented benchmarking script/plan) are captured for latency and concurrent load.
