# Architectural Review Findings

**Reviewer role:** Senior Software Architect  
**Date:** 2026-06-29  
**Documents reviewed:**
- `PROJECT_BRIEF.md`
- `docs/adr/0001-transcription-backend.md`
- `docs/test-specification.md`
- `docs/implementation-roadmap.md`

Findings are grouped by severity. **Errors** are factual mistakes or contradictions that must be corrected before implementation. **Risks** are architectural gaps likely to cause production failures. **Improvements** are valid enhancements without blocking urgency.

> **Resolution status (2026-06-29):** All 18 findings have been addressed in the planning artifacts. No application code existed yet, so every fix landed in the test spec, roadmap, fixture generator, or a new ADR. The cross-cutting risks (R-01, R-02, R-03, R-05, R-06) are recorded as decisions in the new **[ADR-0002](adr/0002-concurrency-and-resource-model.md)**. See the Resolution column in the summary table for where each was fixed.

---

## Errors

### E-01 — `same_audio.mp3` fixture missing from table and generator

TC-402 (MP3 format support) references `same_audio.mp3` as its fixture. This file appears in neither the fixture table in Section 2 of the test specification nor in `tests/generate_fixtures.py`. TC-402 cannot be run.

**Fix:** Add `same_audio.mp3` to the fixture table and add a variant entry in `gen_format_variants()` using `["-c:a", "libmp3lame", "-q:a", "2"]`.

---

### E-02 — ADR Decision block still reads "Proposed:"

The ADR status field was updated to `Approved` but the Decision section still opens with _"Proposed: faster-whisper (`large-v3`)…"_. The body text was not updated to match the status change.

**Fix:** Replace "Proposed:" with "Decision:" (or remove the qualifier) in the Decision section.

---

### E-03 — US-02 health check references pyannote before pyannote is integrated

US-02 (Increment 1) states the health endpoint should return `"models_loaded": true` _"once faster-whisper and pyannote are loaded."_ However, pyannote is not integrated until US-06 (Increment 2). In Increment 1 the service has no knowledge of pyannote.

**Fix:** Scope US-02 acceptance criteria to faster-whisper only. Update the health check in US-06 to also report pyannote readiness once it is integrated.

---

### E-04 — TC-202 requires `speaker` field, but Increment 1 explicitly omits it

TC-202 lists `speaker` as a required field on every segment object. The roadmap states Increment 1 has _"speaker field absent or null."_ TC-202 will fail until Increment 2 is complete, which is by design — but the test specification does not annotate this. A tester running TC-202 after Increment 1 will see a false failure with no explanation.

**Fix:** Add a note to TC-202 stating it requires Increment 2 (diarisation) to be complete before it can pass.

---

### E-05 — TC-503 method references ground-truth text, not ASR output

TC-503 instructs the tester to _"note a distinctive phrase from the ground-truth transcript"_ and then search for it in post-response logs. The ground truth is the TTS script; the ASR output is a model prediction that may differ in wording, punctuation, or capitalisation. Searching for the scripted phrase may miss an actual logging violation, and may also produce false positives/negatives.

**Fix:** The distinctive phrase to search for in logs must be taken from the actual response `segments[].text` fields, not from the ground-truth file.

---

## Risks

### R-01 — Concurrent request safety of pyannote pipeline is unverified

The ADR selects `pyannote/speaker-diarization-3.1` but does not address whether the pyannote pipeline object is safe to call from multiple threads simultaneously. The `Pipeline.__call__` method in pyannote.audio is documented as not thread-safe when sharing a single pipeline instance. Under US-19 (10 concurrent requests), this would produce corrupted results or crashes.

**Required decision before Increment 2:** Either (a) instantiate one pipeline per worker process (process-based concurrency), (b) use a serialisation lock around pipeline calls (serialises diarisation throughput), or (c) pool multiple pipeline instances. The choice has a direct impact on the concurrency architecture established in Increment 5.

---

### R-02 — 90-minute in-memory audio creates significant memory pressure under concurrency

US-05 mandates in-memory audio processing (no disk writes during WAV handling). A 90-minute file decoded to PCM at 16 kHz mono int16 occupies approximately 172 MB of RAM. Under 10 concurrent requests (US-19), this is 1.7 GB of PCM buffers alone, before model weights (~3 GB VRAM for large-v3 float16, ~1.5 GB for int8). This combination is likely to OOM on common deployment hardware.

The roadmap presents US-05 (in-memory) and US-16 (90-min OOM-free) and US-19 (10 concurrent) as independent stories with no acknowledged tension between them.

**Required decision before Increment 4:** Define an explicit memory ceiling for the service and determine whether chunked processing or streaming decoding is needed for large files. Note that chunked processing is compatible with the privacy constraint as long as no chunk is written to disk.

---

### R-03 — No client disconnect cancellation propagation for thread-pool transcription

US-17 requires the service to clean up resources when a client disconnects mid-request. If transcription and diarisation run inside `asyncio.get_event_loop().run_in_executor()` (the typical pattern in FastAPI for blocking model inference), a client disconnect does not cancel the executor thread — the thread continues running until completion and the result is silently discarded. This means an aborted 90-minute request still occupies a worker thread and the full model memory for 90+ minutes.

**Required decision before Increment 4 (US-17):** Choose an explicit cancellation strategy — either accept that work continues after disconnect (and document this as the policy), or use a process-level interrupt mechanism (e.g. `concurrent.futures` cancellation with cooperative checkpoints in the transcription loop).

---

### R-04 — Model loading strategy not defined; affects cold-start time and air-gapped deployments

Neither the ADR nor the roadmap specifies where models are sourced from at startup: downloaded from HuggingFace on first run, downloaded at image build time (baked in), or mounted from a volume. The implications differ significantly:

- Download at startup: internet dependency at boot; cold start can exceed 5 minutes for large-v3 (3 GB download).
- Baked into image: Docker image becomes ~5–8 GB; CI build times increase substantially.
- Volume mount: requires operational workflow to pre-populate the volume.

US-01 says "a single command starts the service" but this promise cannot be kept without a decided model strategy.

**Required decision before US-01:** Document the model sourcing strategy in the ADR consequences or a follow-on ADR.

---

### R-05 — Pyannote RTF overhead excluded from TC-601 latency targets

The ADR consequences note that _"pyannote diarisation adds ~1–3 s latency overhead per file."_ TC-601 defines RTF targets (≤ 0.5 on GPU, ≤ 2.0 on CPU int8) against 30 s audio. The RTF denominator is 30 s, so a 1–3 s pyannote overhead adds 0.03–0.1 to the effective RTF — potentially pushing a near-threshold CPU int8 result over the limit. The RTF targets as written appear to assume transcription time only.

**Fix:** Confirm whether the RTF thresholds are intended to cover total pipeline latency (transcription + diarisation + I/O). If so, the CPU int8 threshold of 2.0 (= 60 s for 30 s audio) may be too tight when diarisation overhead is included.

---

### R-06 — No maximum upload size enforced

No story, test case, or ADR consequence addresses an upper bound on uploaded file size. Without a limit, a sufficiently large upload can exhaust memory (R-02) or consume disk space during format conversion (violating the privacy constraint). A 2-hour 48kHz stereo FLAC could be 800 MB+ before decoding.

**Fix:** Add a US in Increment 3 or 4: define and enforce a maximum upload size (e.g. 500 MB) with a `413 Content Too Large` response.

---

## Improvements

### I-01 — Speaker differentiation in synthetic fixtures is acoustically weak

The fixture generator differentiates speakers using pitch and rate adjustments of the same edge-tts voice (`de-DE-ConradNeural` and `de-DE-KatjaNeural`). For the 5-speaker fixture, three speakers use `ConradNeural` with only ±8–12% rate shifts. Pyannote's diarisation uses speaker embeddings (d-vectors) derived from vocal tract characteristics — rate and pitch shifts of the same voice will produce similar embeddings and are likely to be mis-attributed.

This means TC-303 (DER ≤ 20%) and TC-305 (exactly 2 labels from 2-speaker audio) may be structurally difficult to pass with the current synthetic fixtures. The DER threshold may need to be relaxed for TTS-generated audio, or the fixtures should use two genuinely distinct TTS voices (`de-DE-ConradNeural` vs `de-DE-KatjaNeural` is a good pair — but the 5-speaker test needs three more distinct voices).

---

### I-02 — `clear_de_1spk_60s.ground_truth.json` is generated but not used in any TC

The generator produces a ground-truth file for the 60 s single-speaker German audio. No test case references it as a quality benchmark (TC-304 uses the file only to count speaker labels). Either add a TC-306 measuring WER on the 60 s file as a second quality data point, or remove the ground-truth generation to reduce maintenance surface.

---

### I-03 — No TC verifies German language is detected correctly

TC-301 tests WER on German audio but does not assert that `response.language == "de"`. A service that transcribes correctly but reports `language: "en"` would pass TC-301 but would fail a real integration. Add an assertion to TC-301 or introduce a dedicated TC-206.

---

### I-04 — TC-709 pass criterion is too weak for its stated purpose

TC-709 (5-speaker audio) passes if `distinct speaker count ≥ 2`. This is trivially satisfied by any multi-speaker recording and provides no meaningful signal about 5-speaker handling. The criterion should be ≥ 3 distinct speakers to be informative, with a note acknowledging pyannote's default speaker count cap.

---

### I-05 — No canonical error response schema defined

TC-102, TC-103, TC-104, TC-705–TC-707 all require a JSON body with either an `error` or `detail` key. Two different key names are acceptable per the spec. An implementation that uses `error` everywhere will have different field names from one that uses FastAPI's default `detail` key (from `HTTPException`). The test assertions and client code will need to handle both, or the schema should be normalised to one key.

**Recommendation:** Define a single canonical error envelope in the test spec: `{"error": {"code": "...", "message": "..."}}`. FastAPI's default 422 uses `{"detail": [...]}` — decide up front whether to override this.

---

### I-06 — Audio resampling is implicit but architecturally significant

faster-whisper requires 16 kHz mono PCM. Browser-recorded WebM/Opus is typically 48 kHz stereo. The format decoding story (US-08) implicitly includes resampling, but this is not explicit. Resampling quality (and library choice: ffmpeg, scipy, librosa) affects transcription accuracy, particularly for non-speech frequencies. This should be an explicit implementation note in US-08.

---

### I-07 — Increment 4 robustness stories are fully parallelisable; roadmap does not say so

US-11 through US-17 have no dependencies on each other. The roadmap notes this in the execution notes but does not reflect it in the story descriptions or ordering. For a team working the roadmap, explicitly marking these as parallelisable would reduce delivery time.

---

### I-08 — Existing `docs/adr/FINDINGS.md` conflicts with approved roadmap

The pre-existing `docs/adr/FINDINGS.md` contains three notes: that status cannot be accepted without human intervention (now resolved), that in-memory processing is not a requirement (the roadmap treats US-05 as a firm requirement derived from the privacy brief), and that concurrency handling is premature. The concurrency finding is directly contradicted by TC-602, TC-603, and US-19 in the approved roadmap. This file should be updated or superseded to avoid conflicting guidance to implementers.

---

## Summary table

| ID | Severity | Area | One-line description | Resolution |
|---|---|---|---|---|
| E-01 | Error | Test spec / fixtures | `same_audio.mp3` fixture missing; TC-402 cannot run | ✅ Added to fixture table + `gen_format_variants()`; regenerated |
| E-02 | Error | ADR | Decision body still reads "Proposed:" after approval | ✅ ADR-0001 Decision now reads "Decision:" |
| E-03 | Error | Roadmap | US-02 references pyannote before it exists (Increment 1) | ✅ US-02 scoped to whisper; US-06 extends health to pyannote |
| E-04 | Error | Test spec / roadmap | TC-202 will fail in Increment 1 by design — not annotated | ✅ TC-202 gains an "Increment gate" note |
| E-05 | Error | Test spec | TC-503 searches ground-truth text, not actual ASR output | ✅ TC-503 now extracts the span from the real response |
| R-01 | Risk | Architecture | pyannote pipeline thread-safety under concurrent load unverified | ✅ ADR-0002 §1: private model instances per worker, no sharing |
| R-02 | Risk | Architecture | In-memory + 90-min audio + 10 concurrent = likely OOM | ✅ ADR-0002 §3: bounded concurrency caps resident buffers; US-16 |
| R-03 | Risk | Architecture | Client disconnect does not cancel executor-thread transcription | ✅ ADR-0002 §4 cancellation policy; US-17 updated |
| R-04 | Risk | Operations | Model loading strategy undefined; breaks "single command" promise | ✅ ADR-0001: weights baked into image at build time |
| R-05 | Risk | Test spec | RTF targets may not include pyannote diarisation overhead | ✅ ADR-0002 §5 + test-spec §3: RTF defined as full-pipeline |
| R-06 | Risk | Architecture | No upload size limit; large files can OOM or violate privacy constraint | ✅ ADR-0002 §3; US-23; TC-711/712 |
| I-01 | Improvement | Fixtures | TTS speaker differentiation too weak for reliable DER measurement | ✅ Generator uses 5 genuinely distinct de-DE voices |
| I-02 | Improvement | Test spec | 60 s ground-truth generated but unused as quality benchmark | ✅ Added TC-306 (WER on 60 s single-speaker file) |
| I-03 | Improvement | Test spec | No TC verifies `language` field value for German audio | ✅ Added TC-205 (asserts `language == "de"`) |
| I-04 | Improvement | Test spec | TC-709 pass criterion (≥ 2 speakers) too weak for 5-speaker test | ✅ Raised to ≥ 3 distinct speakers |
| I-05 | Improvement | Test spec | No canonical error response schema; `error` vs `detail` ambiguous | ✅ Test-spec §3: canonical `{error:{code,message}}` envelope |
| I-06 | Improvement | Roadmap | Audio resampling to 16 kHz not explicit in US-08 | ✅ US-08 states 16 kHz mono int16 downmix + resample |
| I-07 | Improvement | Roadmap | Increment 4 stories are parallelisable but not marked as such | ✅ Increment 4 header marks US-11–US-17 parallelisable |
| I-08 | Improvement | Docs | `docs/adr/FINDINGS.md` conflicts with approved roadmap on concurrency | ✅ Old file annotated as resolved/superseded |
