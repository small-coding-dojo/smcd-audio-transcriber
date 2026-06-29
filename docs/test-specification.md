# Test Specification — Audio Transcriber Service

**Version:** 1.1  
**Date:** 2026-06-29  
**Linked brief:** [PROJECT_BRIEF.md](../PROJECT_BRIEF.md)  
**Linked ADRs:** [ADR-0001](adr/0001-transcription-backend.md), [ADR-0002](adr/0002-concurrency-and-resource-model.md)

---

## 1. Scope

This specification covers acceptance testing of the ClearVoice Audio Transcriber Service after implementation is complete. It is not a unit-test guide — it validates observable, end-to-end behaviour against the requirements in the project brief.

Tests are grouped into eight categories. Run them in order: contract failures block everything downstream.

---

## 2. Test Fixtures

Create these files under `tests/fixtures/` before executing any test cases. Ground-truth transcripts and speaker-turn tables for quality tests must be prepared by a human reviewer from known recordings.

| Fixture | Description |
|---|---|
| `clear_de_2spk_30s.wav` | 30 s clear German speech, 2 distinct speakers, known transcript + speaker turns |
| `clear_de_1spk_60s.mp3` | 60 s clear German, 1 speaker, known transcript |
| `clear_en_1spk_10s.wav` | 10 s clear English, used for format-conversion checks |
| `silence_10s.wav` | 10 s of pure silence |
| `noisy_speech_30s.wav` | 30 s speech with constant background noise (e.g. fan or crowd) |
| `long_90min.mp3` | 90-minute recording (any content) |
| `very_short_200ms.wav` | 200 ms speech clip |
| `same_audio.mp3` | Same content as `clear_en_1spk_10s.wav`, re-encoded to MP3 |
| `same_audio.flac` | Same content as `clear_en_1spk_10s.wav`, re-encoded to FLAC |
| `same_audio.m4a` | Same content, M4A/AAC container |
| `same_audio.ogg` | Same content, OGG Vorbis |
| `same_audio.webm` | Same content, WebM/Opus (standard browser-recorded format) |
| `same_audio.mp4` | Same content, MP4 container |
| `corrupt.wav` | Valid WAV header followed by random bytes |
| `not_audio.pdf` | Any PDF file |
| `fake_wav.wav` | A PDF file renamed with a `.wav` extension |
| `empty.wav` | Zero-byte file |
| `5speaker_30s.wav` | 30 s audio with 5 distinct speakers |

**Ground-truth tables required** (human-prepared, stored alongside fixtures):

- `clear_de_2spk_30s.ground_truth.json` — array of `{start, end, text, speaker}` objects
- `clear_de_1spk_60s.ground_truth.json` — same format, one speaker label throughout

---

## 3. Acceptance Thresholds

Quantitative targets referenced by test cases below.

| Metric | Definition | Pass threshold |
|---|---|---|
| WER | Word Error Rate against ground-truth transcript | ≤ 15 % (German, clear speech) |
| Timestamp delta | \|predicted\_boundary − ground\_truth\_boundary\| | ≤ 0.5 s per segment |
| DER | Diarization Error Rate (missed + false alarm + confusion) | ≤ 20 % (2-speaker, clear speech) |
| RTF (GPU) | processing\_time / audio\_duration | ≤ 0.5 |
| RTF (CPU int8) | processing\_time / audio\_duration | ≤ 2.0 |
| Concurrency degradation | p95 latency under 10 concurrent requests vs. single-request baseline | ≤ 3 × baseline |

Choose the GPU or CPU threshold based on the hardware the service runs on during testing; document which applies.

**RTF covers the full pipeline.** Per [ADR-0002](adr/0002-concurrency-and-resource-model.md) §5, the RTF thresholds are measured end-to-end: decode + resample + transcription + diarisation + alignment + JSON serialisation — not transcription time alone. The ~1–3 s pyannote overhead noted in ADR-0001 is included and sits within the stated thresholds.

**Concurrency degradation is measured at a documented worker count.** Per ADR-0002 §1, the p95 target is evaluated against a deployment sized to the offered load. The number of worker processes used for TC-603 must be recorded alongside the hardware profile, or the result is not interpretable.

### Canonical error schema

All non-2xx responses return the same JSON envelope so clients parse one shape (resolves the earlier `error` vs `detail` ambiguity):

```json
{ "error": { "code": "string_constant", "message": "human-readable description" } }
```

`code` is a stable machine token (e.g. `missing_file`, `unsupported_format`, `file_too_large`, `audio_too_long`, `empty_file`, `overloaded`). FastAPI's default `{"detail": ...}` body for `HTTPException`/422 is overridden by a global exception handler to this envelope. Test cases below that say "JSON with an `error` key" expect this shape.

**Negative-path status codes** (defined in ADR-0002 §2–3):

| Status | `code` | Condition |
|---|---|---|
| `400` | `missing_file` / `bad_request` | Missing or malformed file field |
| `413` | `file_too_large` | Upload exceeds `MAX_UPLOAD_BYTES` |
| `415` / `422` | `unsupported_format` | Content is not decodable audio |
| `422` | `audio_too_long` | Audio duration exceeds `MAX_AUDIO_DURATION_S` |
| `400` | `empty_file` | Zero-byte upload |
| `503` | `overloaded` | Queue full; includes `Retry-After` |

---

## 4. Test Cases

### TC-1xx — API Contract

These tests verify the HTTP interface exists and enforces its inputs correctly. Use any valid audio file (e.g. `clear_en_1spk_10s.wav`) unless stated otherwise.

---

**TC-101 — Endpoint accepts POST with audio file**

- **Requirement:** REQ-CORE-1 (accept uploaded audio)
- **Type:** Automated
- **Input:** `POST /transcribe` with `multipart/form-data`, field name `file`, file `clear_en_1spk_10s.wav`
- **Expected:** HTTP 200
- **Pass if:** Status code is 200

---

**TC-102 — Missing file field returns 400**

- **Requirement:** REQ-CORE-1
- **Type:** Automated
- **Input:** `POST /transcribe` with empty multipart body (no `file` field)
- **Expected:** HTTP 400 with JSON error body
- **Pass if:** Status 400; body is valid JSON with an `error` or `detail` key describing the problem

---

**TC-103 — Wrong field name returns 400**

- **Requirement:** REQ-CORE-1
- **Type:** Automated
- **Input:** `POST /transcribe` with multipart field named `audio` (not `file`) containing a valid WAV
- **Expected:** HTTP 400
- **Pass if:** Status 400 (or 422); body is valid JSON with descriptive error

---

**TC-104 — Non-multipart body returns 400**

- **Requirement:** REQ-CORE-1
- **Type:** Automated
- **Input:** `POST /transcribe` with `Content-Type: application/json`, body `{}`
- **Expected:** HTTP 400 or 415
- **Pass if:** Status 4xx; service does not crash (no 500)

---

**TC-105 — Response Content-Type is JSON**

- **Requirement:** REQ-QUAL-3 (structured, easy to consume)
- **Type:** Automated
- **Input:** Valid POST with `clear_en_1spk_10s.wav`
- **Pass if:** Response `Content-Type` header contains `application/json`

---

**TC-106 — Response body is valid JSON**

- **Requirement:** REQ-QUAL-3
- **Type:** Automated
- **Input:** Valid POST with `clear_en_1spk_10s.wav`
- **Pass if:** Body parses without error as JSON

---

### TC-2xx — Response Schema

These tests verify the structure of a successful response using `clear_de_2spk_30s.wav`.

---

**TC-201 — Top-level fields present**

- **Requirement:** REQ-CORE-2 (timestamps), REQ-CORE-3 (diarisation), REQ-QUAL-3 (structured)
- **Type:** Automated
- **Pass if:** Response JSON contains at minimum:
  - `segments` — array (may be empty for silence)
  - `duration` — numeric, seconds (float)
  - `language` — string (detected or declared language code)

---

**TC-202 — Segment object fields**

- **Requirement:** REQ-CORE-2, REQ-CORE-3
- **Type:** Automated
- **Increment gate:** The `speaker` assertion requires diarisation (roadmap Increment 2 / US-06). Before Increment 2 the service emits segments without a `speaker` field by design; run the reduced form (assert `start`/`end`/`text` only) until Increment 2 is complete, then enable the full assertion.
- **Pass if:** Every object in `segments` contains:
  - `start` — number (seconds, float)
  - `end` — number (seconds, float)
  - `text` — string
  - `speaker` — string (e.g. `"SPEAKER_00"`) *(from Increment 2 onward)*

---

**TC-203 — Segment time ordering and validity**

- **Requirement:** REQ-CORE-2
- **Type:** Automated
- **Pass if:** For every segment, `start < end`; segments are sorted ascending by `start`; no segment `end` exceeds the audio `duration` by more than 0.5 s

---

**TC-204 — Speaker label consistency**

- **Requirement:** REQ-CORE-3
- **Type:** Automated
- **Pass if:** All `speaker` values across the response are drawn from a fixed label set (no label changes spelling or casing mid-response); labels are non-empty strings

---

**TC-205 — Language detected correctly for German audio**

- **Requirement:** REQ-QUAL-3 (structured); ADR-0001 (German language)
- **Type:** Automated
- **Fixture:** `clear_de_2spk_30s.wav`
- **Rationale:** A service that transcribes accurately but mislabels the language would pass TC-301 yet break a real integration. This isolates the `language` value.
- **Pass if:** Response `language` equals `"de"`

---

### TC-3xx — Transcription Quality

These tests require ground-truth fixtures and a WER/DER calculation script.

---

**TC-301 — German transcription accuracy**

- **Requirement:** REQ-QUAL-1 (accurate for clear recordings); ADR-0001 (German language)
- **Type:** Automated (with ground-truth fixture)
- **Fixture:** `clear_de_2spk_30s.wav` + `clear_de_2spk_30s.ground_truth.json`
- **Method:** Concatenate all `text` fields from the response into a single string. Compute WER against the concatenated ground-truth transcript using a standard normaliser (lower-case, strip punctuation).
- **Pass if:** WER ≤ 15 %

---

**TC-302 — Segment timestamp accuracy**

- **Requirement:** REQ-CORE-2 (timestamps)
- **Type:** Automated (with ground-truth fixture)
- **Fixture:** `clear_de_2spk_30s.ground_truth.json`
- **Method:** For each ground-truth segment boundary, find the nearest predicted boundary. Compute absolute delta.
- **Pass if:** Median delta ≤ 0.5 s; no single boundary exceeds 2.0 s delta

---

**TC-303 — Speaker diarisation correctness (2 speakers)**

- **Requirement:** REQ-CORE-3 (speaker identification)
- **Type:** Automated (with ground-truth fixture)
- **Fixture:** `clear_de_2spk_30s.wav` + `clear_de_2spk_30s.ground_truth.json`
- **Method:** Compute Diarization Error Rate using `pyannote.metrics` or equivalent. Map predicted speaker labels to ground-truth labels via Hungarian algorithm before scoring.
- **Pass if:** DER ≤ 20 %

---

**TC-304 — Single-speaker recording produces one speaker label**

- **Requirement:** REQ-CORE-3
- **Type:** Automated
- **Fixture:** `clear_de_1spk_60s.mp3`
- **Pass if:** Set of distinct `speaker` values across all segments has exactly 1 member

---

**TC-305 — Two-speaker recording produces exactly two speaker labels**

- **Requirement:** REQ-CORE-3
- **Type:** Automated
- **Fixture:** `clear_de_2spk_30s.wav`
- **Pass if:** Set of distinct `speaker` values has exactly 2 members

---

**TC-306 — German transcription accuracy (single speaker, longer sample)**

- **Requirement:** REQ-QUAL-1 (accurate for clear recordings); ADR-0001 (German language)
- **Type:** Automated (with ground-truth fixture)
- **Fixture:** `clear_de_1spk_60s.mp3` + `clear_de_1spk_60s.ground_truth.json`
- **Method:** Same as TC-301 — concatenate response `text`, compute WER against concatenated ground truth with the standard normaliser. Provides a second quality data point on a longer single-speaker sample and exercises the previously-unused ground-truth fixture.
- **Pass if:** WER ≤ 15 %

---

### TC-4xx — Audio Format Support

Each test uses the same underlying audio encoded in a different container/codec. Compare the transcript text to `clear_en_1spk_10s.wav` output: both must produce recognisably equivalent transcripts (same words, ignoring minor WER variance).

---

**TC-401 — WAV (PCM 16-bit)**  
Fixture: `clear_en_1spk_10s.wav` — baseline; must return HTTP 200

**TC-402 — MP3**  
Fixture: `same_audio.mp3` — must return HTTP 200 with non-empty `segments`

**TC-403 — FLAC**  
Fixture: `same_audio.flac` — must return HTTP 200 with non-empty `segments`

**TC-404 — M4A / AAC**  
Fixture: `same_audio.m4a` — must return HTTP 200 with non-empty `segments`

**TC-405 — OGG Vorbis**  
Fixture: `same_audio.ogg` — must return HTTP 200 with non-empty `segments`

**TC-406 — WebM / Opus** *(browser-recorded format — high priority)*  
Fixture: `same_audio.webm` — must return HTTP 200 with non-empty `segments`

**TC-407 — MP4 (audio track)**  
Fixture: `same_audio.mp4` — must return HTTP 200 with non-empty `segments`

For TC-402 through TC-407, **pass if** status is 200 and the transcript WER against the `clear_en_1spk_10s.wav` ground-truth is ≤ 20 % (slightly relaxed to allow codec-induced distortion).

---

### TC-5xx — Privacy and Data Retention

> **Important:** The ADR permits temporary files during processing but requires they are deleted before the response is returned. Tests here verify post-response state, not mid-request state.

---

**TC-501 — No audio files remain on disk after response**

- **Requirement:** REQ-PRIV-1, REQ-PRIV-2
- **Type:** Instrumented
- **Method:**
  1. Record all files under `/tmp`, the service working directory, and any configured temp paths before the request.
  2. Send `POST /transcribe` with `clear_de_2spk_30s.wav`.
  3. Wait for HTTP response.
  4. Enumerate all new files created since step 1. For each new file, check whether it contains audio data (non-zero size, matches a known audio magic byte sequence or contains a fragment of the uploaded file's bytes).
- **Pass if:** Zero files containing audio data persist after the response is delivered

---

**TC-502 — Audio content does not appear in application logs**

- **Requirement:** REQ-PRIV-2
- **Type:** Instrumented
- **Method:**
  1. Prepare a WAV file containing a known unique byte sequence embedded in the audio payload (e.g. embed a fixed 16-byte marker in the PCM data).
  2. Capture all log output (stdout, stderr, log files) during and after the request.
  3. Search captured logs for the unique marker sequence (both raw bytes and base64-encoded form).
- **Pass if:** Marker not found in logs

---

**TC-503 — Transcript text does not appear in application logs after response**

- **Requirement:** REQ-PRIV-3
- **Type:** Instrumented
- **Method:**
  1. Transcribe `clear_de_1spk_60s.mp3`. From the **actual response** `segments[].text`, extract a distinctive span of ≥ 5 consecutive words. Use the model's own output, not the ground-truth script — the ASR prediction may differ from the script in wording, casing, or punctuation, and only the real output is guaranteed to be present if the service logs transcript content.
  2. Capture all log output emitted *after* the response was sent.
  3. Search the captured logs for that span (and for a normalised, lower-cased, punctuation-stripped variant).
- **Pass if:** The span is not found in post-response logs

---

**TC-504 — No audio data written to structured storage**

- **Requirement:** REQ-PRIV-1, REQ-PRIV-2
- **Type:** Instrumented (if applicable)
- **Precondition:** Applies only if the service uses a database, cache, or message queue.
- **Method:** Monitor all writes to any persistent store during a request. Inspect written data for audio binary content.
- **Pass if:** No audio bytes written; or no persistent store is used (auto-pass)

---

### TC-6xx — Performance

Run performance tests on the target hardware (GPU or CPU int8) and record which hardware profile applies. Results are only comparable when hardware is documented.

---

**TC-601 — Single-request latency meets RTF target**

- **Requirement:** REQ-PERF-1 (reasonable time relative to audio length)
- **Type:** Automated (timed)
- **Fixture:** `clear_de_2spk_30s.wav` (30 s audio)
- **Method:** Time from request sent to full response body received. Repeat 5 times; take the median.
- **Pass if (GPU):** Median ≤ 15 s (RTF 0.5)  
  **Pass if (CPU int8):** Median ≤ 60 s (RTF 2.0)

---

**TC-602 — Concurrent requests complete without server errors**

- **Requirement:** REQ-PERF-2 (multiple concurrent requests)
- **Type:** Automated (load)
- **Method:** Send 10 simultaneous `POST /transcribe` requests with `clear_de_2spk_30s.wav`. All requests must complete (no hanging).
- **Pass if:** Zero 5xx responses; all 10 return valid transcripts

---

**TC-603 — Concurrency does not degrade latency beyond 3×**

- **Requirement:** REQ-PERF-2
- **Type:** Automated (load)
- **Method:** Use the p95 latency from TC-601 as baseline. Run 10 concurrent requests (same fixture). Measure p95 latency across all 10.
- **Pass if:** Concurrent p95 ≤ 3 × single-request baseline p95

---

**TC-604 — No memory leak across sequential requests**

- **Requirement:** REQ-PERF-2, REQ-EVAL-4 (resource consumption)
- **Type:** Instrumented
- **Method:** Record resident memory (RSS) of the service process before the test. Send 20 sequential requests with `clear_en_1spk_10s.wav`. Record RSS after each. Compare RSS after request 20 to RSS after request 1.
- **Pass if:** RSS growth after request 20 vs. after request 1 is ≤ 50 MB (model weights excluded from baseline; only incremental growth counts)

---

### TC-7xx — Robustness and Edge Cases

---

**TC-701 — Silence-only audio returns empty transcript**

- **Requirement:** REQ-QUAL-2 (graceful edge case handling)
- **Fixture:** `silence_10s.wav`
- **Pass if:** HTTP 200; `segments` is an empty array `[]`; no 5xx

---

**TC-702 — Noisy audio returns 200 without crash**

- **Requirement:** REQ-QUAL-2
- **Fixture:** `noisy_speech_30s.wav`
- **Pass if:** HTTP 200; response is valid JSON; service process remains alive after the request

---

**TC-703 — Very long recording completes**

- **Requirement:** REQ-QUAL-2 (very long recordings)
- **Fixture:** `long_90min.mp3`
- **Method:** Send request with a long timeout (2 hours). Monitor service memory.
- **Pass if:** HTTP 200 eventually returned; no OOM crash; no 5xx

---

**TC-704 — Very short audio handled gracefully**

- **Requirement:** REQ-QUAL-2
- **Fixture:** `very_short_200ms.wav`
- **Pass if:** HTTP 200; `segments` is either empty or contains one entry; no 5xx

---

**TC-705 — Unsupported file type returns 4xx**

- **Requirement:** REQ-QUAL-2 (unsupported format)
- **Fixture:** `not_audio.pdf`
- **Pass if:** HTTP 4xx (400, 415, or 422); body is valid JSON with an `error` key; no 5xx

---

**TC-706 — File with audio extension but non-audio content returns 4xx**

- **Requirement:** REQ-QUAL-2
- **Fixture:** `fake_wav.wav` (PDF content, .wav name)
- **Pass if:** HTTP 4xx; body is valid JSON with an `error` key; service does not crash

---

**TC-707 — Zero-byte file returns 400**

- **Requirement:** REQ-QUAL-2
- **Fixture:** `empty.wav`
- **Pass if:** HTTP 400; body is valid JSON with an `error` key

---

**TC-708 — Corrupted audio file does not return 500**

- **Requirement:** REQ-QUAL-2
- **Fixture:** `corrupt.wav`
- **Pass if:** HTTP 4xx or 200 with empty segments; specifically, **not** HTTP 5xx; service remains alive

---

**TC-709 — Five-speaker audio handled without crash**

- **Requirement:** REQ-QUAL-2
- **Fixture:** `5speaker_30s.wav`
- **Pass if:** HTTP 200; `segments` non-empty; distinct `speaker` count ≥ 3; no 5xx  
  *Note: the fixture uses five genuinely distinct edge-tts voices (3 male, 2 female), so the diariser should resolve well above two clusters. A `≥ 2` bar is trivially met by any multi-speaker audio and gives no signal about 5-speaker handling; `≥ 3` confirms the diariser separates more than a single male/female split. Exact-5 is not required — pyannote may cap or merge speakers — but it must not collapse five voices to two.*

---

**TC-710 — Client disconnect does not leave service in broken state**

- **Requirement:** REQ-PERF-2 (handles concurrent load); REQ-EVAL-1 (robustness)
- **Type:** Instrumented
- **Method:** Send `POST /transcribe` with `long_90min.mp3`. After 5 s, close the TCP connection from the client side. Then immediately send a second valid request with `clear_en_1spk_10s.wav`.
- **Pass if:** Second request returns HTTP 200 with valid transcript; service process is still alive; no resource leak (open file handles or threads) visible after the second request completes

---

**TC-711 — Oversized upload is rejected with 413**

- **Requirement:** REQ-QUAL-2; [ADR-0002](adr/0002-concurrency-and-resource-model.md) §3 (resource ceilings)
- **Type:** Automated
- **Fixture:** Generated at test time (not stored): a file exceeding `MAX_UPLOAD_BYTES` (e.g. `dd`/ffmpeg-produced filler just over the configured limit). Keeping it out of the repo avoids committing a 100 MB+ binary.
- **Method:** POST the oversized file to `/transcribe`.
- **Pass if:** HTTP `413`; body is the canonical error envelope with `code: "file_too_large"`; the full body is not buffered into memory (service RSS does not spike by the upload size); no `5xx`

---

**TC-712 — Over-duration audio is rejected with 422**

- **Requirement:** REQ-QUAL-2; ADR-0002 §3
- **Type:** Automated
- **Fixture:** Generated at test time (not stored): a low-bitrate file whose probed duration exceeds `MAX_AUDIO_DURATION_S` but whose byte size stays under `MAX_UPLOAD_BYTES` (e.g. a long stretch of silence or looped speech encoded at a low bitrate), isolating the duration check from the size check.
- **Method:** POST the over-duration file to `/transcribe`.
- **Pass if:** HTTP `422`; body is the canonical error envelope with `code: "audio_too_long"`; rejection happens after a metadata probe, before full decode; no `5xx`

---

**TC-713 — Excess concurrency is shed with 503, not OOM**

- **Requirement:** REQ-PERF-2; ADR-0002 §2 (backpressure)
- **Type:** Automated (load)
- **Method:** Send simultaneous requests well beyond the configured `QUEUE_DEPTH` (e.g. `QUEUE_DEPTH + 20`) with `clear_de_2spk_30s.wav`.
- **Pass if:** Over-capacity requests receive `503` with a `Retry-After` header and the canonical error envelope (`code: "overloaded"`); admitted requests still return valid `200` transcripts; the service does not crash or OOM

---

### TC-8xx — Streaming (Extra Credit)

These tests apply only if the streaming endpoint is implemented. Skip if not.

---

**TC-801 — Streaming endpoint exists**

- **Type:** Automated
- **Method:** Connect to the streaming endpoint (WebSocket or SSE). Send audio data for `clear_de_1spk_60s.mp3`.
- **Pass if:** Connection is accepted without HTTP 404 or 501

---

**TC-802 — Transcript segments arrive incrementally**

- **Requirement:** EXTRA-1 (real-time segments)
- **Type:** Automated (timed)
- **Method:** Record the wall-clock time of each received segment event. Audio duration is 60 s.
- **Pass if:** At least one segment is received before the full audio duration has elapsed (i.e. at least one event arrives < 60 s after streaming begins)

---

**TC-803 — Server cleans up on client disconnect**

- **Requirement:** REQ-PRIV-1; REQ-PERF-2
- **Type:** Instrumented
- **Method:** Connect to streaming endpoint, begin sending audio, then close the connection after 3 s. Monitor open file handles and thread count for the service process over the next 10 s.
- **Pass if:** No orphaned threads or open audio file handles remain 10 s after disconnect; service remains responsive to new requests

---

## 5. Requirement Coverage Matrix

| Requirement | Test cases |
|---|---|
| REQ-CORE-1: Accept audio, return transcript | TC-101, TC-102, TC-103, TC-104 |
| REQ-CORE-2: Timestamps | TC-201, TC-202, TC-203, TC-302 |
| REQ-CORE-3: Speaker diarisation | TC-201, TC-202, TC-204, TC-303, TC-304, TC-305 |
| REQ-CORE-4: Common audio formats | TC-401–TC-407 |
| REQ-PRIV-1: No audio stored beyond request | TC-501, TC-504, TC-803 |
| REQ-PRIV-2: No disk write/log/retain after response | TC-501, TC-502 |
| REQ-PRIV-3: No transcript logged/stored after response | TC-503 |
| REQ-PERF-1: Reasonable latency relative to audio length | TC-601 |
| REQ-PERF-2: Multiple concurrent requests | TC-602, TC-603, TC-604, TC-710, TC-713 |
| REQ-QUAL-1: Accurate for clear recordings | TC-301, TC-306 |
| REQ-QUAL-2: Graceful edge case handling | TC-701–TC-713 |
| REQ-QUAL-3: Structured response | TC-105, TC-106, TC-201, TC-202, TC-203, TC-204, TC-205 |
| ADR-0001: German language | TC-205, TC-301, TC-302, TC-303, TC-304, TC-305, TC-306 |
| ADR-0002: Resource ceilings & backpressure | TC-711, TC-712, TC-713 |
| EXTRA: Streaming | TC-801, TC-802, TC-803 |

---

## 6. Test Execution Notes

**Ordering:** Run TC-1xx first. Failures here indicate the endpoint is missing or broken; all other categories depend on a working endpoint.

**Test types:**
- *Automated* — can be scripted with `pytest` + `httpx`; suitable for CI
- *Instrumented* — requires OS-level monitoring (filesystem watchers, `/proc/<pid>/fd`, log capture); run in a controlled environment, not in a shared CI runner

**Hardware documentation:** Record CPU model, GPU model (if present), RAM, and quantisation setting (`int8` / `float16` / `float32`) in the test report. Latency results are meaningless without this context.

**Privacy tests:** Run TC-5xx in an isolated environment where log output is fully captured. Do not run these against a shared logging infrastructure that may buffer or drop lines.

**WER/DER tooling:** Use `jiwer` (Python) for WER; `pyannote.metrics` for DER. Pin versions in the test requirements file to ensure reproducible scores.
