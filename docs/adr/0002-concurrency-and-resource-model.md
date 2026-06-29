# ADR-0002: Concurrency, Resource Limits, and Request Lifecycle

**Date:** 2026-06-29
**Status:** Approved
**Deciders:** Engineering

---

## Context

[ADR-0001](0001-transcription-backend.md) selected self-hosted faster-whisper + pyannote.audio. That choice makes transcription and diarisation **compute-bound, in-process model inference** rather than calls to an elastic cloud API. The project brief additionally requires the service to handle **multiple concurrent requests without degrading**, to **respond within a reasonable time relative to audio length**, and to **never persist audio beyond the request**.

The architectural review ([FINDINGS.md](../FINDINGS.md)) raised five coupled risks that cannot be answered story-by-story because they share one root cause — a single machine with finite compute and memory must serve concurrent heavy inference:

- **R-01** pyannote `Pipeline.__call__` is not thread-safe when one instance is shared across threads.
- **R-02** In-memory decode of long audio under concurrency can exhaust RAM/VRAM.
- **R-03** A client disconnect does not, by default, cancel inference already running in a thread executor.
- **R-05** The test-spec RTF targets did not state whether they cover diarisation overhead.
- **R-06** No maximum upload size was defined, leaving the service open to memory exhaustion.

This ADR decides the concurrency model, the resource ceilings, and the request lifecycle once, so the roadmap stories and test cases can reference a single coherent design.

---

## Decision Drivers

- Model inference is CPU/GPU-bound and does not safely share a single model instance across threads (R-01).
- A single compute device serialises heavy inference: throughput scales with **process** replicas, not threads.
- Privacy constraint: "in-memory" means **not persisted to disk**, not "entire file resident at once" — but bounded memory is still required under load.
- The service must remain predictable (no OOM, no 5xx) under both oversized input and excess concurrency.

---

## Decision

### 1. Concurrency model — process workers, each owning private model instances

- The HTTP layer is **async** (FastAPI on uvicorn). It accepts requests, validates them, and hands the decoded-audio work to a model worker. The event loop is never blocked by inference.
- Each **worker process** loads its **own private** faster-whisper instance and its **own private** pyannote pipeline at startup. Model instances are **never shared between threads or processes** — this is the direct resolution of R-01.
- Within a worker, heavy inference is serialised by a bounded in-process semaphore (**one in-flight inference per model instance**). CTranslate2 (faster-whisper) and pyannote already saturate the device with internal threads; running two inferences concurrently on one device yields no speed-up and risks VRAM exhaustion.
- Horizontal concurrency is achieved by running **N worker processes** (`uvicorn --workers N`, or N replicas behind a load balancer), sized to the hardware (`N ≈ device_count`, or memory-bounded on CPU). Throughput scales with N.

**Consequence for the latency-under-load target (test-spec TC-603, "p95 ≤ 3× single-request baseline"):** this is measured against a deployment **sized to the offered load**. On a single device, deep concurrency necessarily queues, so the worker count for the load test is set so that the 95th-percentile request waits at most ~2 waves. The test report must record the worker count used (added to the existing requirement to record hardware).

### 2. Backpressure — bounded queue, then `503`

- Admitted concurrency is bounded by a configurable **queue depth** (default 32), set comfortably **above** the test suite's concurrency (10) so TC-602 sees zero 5xx.
- Requests arriving when the queue is full receive **`503 Service Unavailable`** with a `Retry-After` header. This is deliberate backpressure: shedding load is correct behaviour, preferable to OOM-killing the process and failing every in-flight request.

### 3. Resource ceilings (resolves R-02, R-06)

- **Maximum upload size:** `MAX_UPLOAD_BYTES`, default **100 MB**. Enforced by streaming the request body and aborting with **`413 Content Too Large`** once the limit is exceeded — the whole body is never buffered to measure it.
- **Maximum audio duration:** `MAX_AUDIO_DURATION_S`, default **7200 s (2 h)**. Probed from the container metadata before full decode; over-limit input is rejected with **`422`**. The cap sits above the 90-minute robustness fixture (TC-703) with headroom.
- **Peak per-request memory is bounded by bounding concurrency, not by chunking.** With worker-level serialisation, only **N** decoded buffers are resident at once. A 90-minute file at 16 kHz mono int16 is ~172 MB; `N = 4` workers ⇒ < 1 GB of PCM, predictable and within typical hardware. Chunked/streaming decode remains an available optimisation for very long files but is **not** required to meet the targets — bounded concurrency is the primary lever. This reconciles US-05 (in-memory), US-16 (90-min), and US-19 (10 concurrent), which the review correctly flagged as being in unacknowledged tension.

### 4. Request lifecycle and cancellation (resolves R-03)

- faster-whisper transcription consumes a **segment generator**. Between segments the handler checks `await request.is_disconnected()` and, on disconnect, **stops iterating and frees the worker**. Cancellation granularity is therefore one segment (typically a few seconds of audio) — bounded, not unbounded, waste.
- pyannote diarisation is a **single blocking call** that cannot be interrupted mid-call. **Policy:** an in-flight diarisation runs to completion, but its result is discarded and the worker slot is released immediately afterward; it is never the case that a disconnected request holds a slot indefinitely.
- A configurable **hard per-request timeout** (`REQUEST_TIMEOUT_S`, default 1.5 × `MAX_AUDIO_DURATION_S` at the worst supported RTF) bounds worst-case slot occupancy even absent a disconnect.
- The streaming endpoint (Increment 6) cancels naturally at chunk boundaries when the socket closes.

### 5. Latency budget definition (resolves R-05)

The RTF targets in the test specification (GPU ≤ 0.5, CPU int8 ≤ 2.0) are hereby defined to cover the **entire request pipeline**: decode + resample + transcription + diarisation + alignment + JSON serialisation. ADR-0001 notes pyannote adds ~1–3 s per file; against the 30 s latency fixture this is well inside the existing thresholds (15 s GPU / 60 s CPU), so the thresholds stand — they are simply clarified as **full-pipeline**, not transcription-only.

---

## Consequences

- Deployment scales by **adding worker processes/replicas**, each needing a full copy of model memory (~3 GB VRAM float16, or ~1.5 GB RAM int8). Operators size N to their device count and memory budget; this is documented in the README.
- The service exposes new tunables: `MAX_UPLOAD_BYTES`, `MAX_AUDIO_DURATION_S`, `QUEUE_DEPTH`, `REQUEST_TIMEOUT_S`, `WORKERS`. All have safe defaults.
- New negative-path responses enter the contract: **`413`** (too large), **`422`** (too long / unprocessable), **`503`** (overloaded). These are added to the test specification.
- TC-603's load test must document worker count alongside hardware, or its result is not interpretable.
- The disconnect policy is honest about its one limitation (an in-flight pyannote call is not mid-call interruptible) rather than implying perfect immediate cancellation.
