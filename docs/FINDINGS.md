# QA Review Findings — Architecture Documentation Alignment

**Date:** 2026-07-06
**Reviewer:** QA
**Scope:** [`docs/architecture.md`](architecture.md) verified against
[PROJECT_BRIEF.md](../PROJECT_BRIEF.md), [ADR-0001](adr/0001-transcription-backend.md),
[ADR-0002](adr/0002-concurrency-and-resource-model.md),
[implementation-roadmap.md](implementation-roadmap.md),
[test-specification.md](test-specification.md), the README, and the code
(`src/`, `Dockerfile`, `docker-compose.yml`, `pyproject.toml`).

**Workflow:** as with the previous architectural review, each finding is
resolved with a linked commit and this file is deleted once all items are
closed.

---

## Verdict

**Largely aligned.** Model choices, configuration defaults, concurrency and
cancellation policy, deployment details, and built-vs-planned status markers
all trace correctly to their sources. Two medium findings, two low, and two
informational items follow.

Verified as correct (no action): faster-whisper `large-v3` + pyannote 3.1 and
build-time weight baking (ADR-0001); process-worker concurrency, backpressure,
memory figures, and disconnect policy (ADR-0002); all tunable defaults
(`MAX_UPLOAD_BYTES` 100 MB, `MAX_AUDIO_DURATION_S` 7200 s, `QUEUE_DEPTH` 32);
Docker/deployment details; increment and story attributions; "no storage tier"
consistent with TC-504 auto-pass.

---

## Findings

| ID | Severity | Affected document | Summary | Status |
|---|---|---|---|---|
| F-01 | Medium | `architecture.md` (§5, §6); ADR-0002 §1 wording | Decode shown before worker-slot acquisition, contradicting ADR-0002 §3's memory bound | Resolved — `d98ab8f` |
| F-02 | Medium | `architecture.md` §9 | Error contract lists only 413/422/503; test spec §3 also defines 400 and 415 codes and the envelope shape | Resolved — `d98ab8f` |
| F-03 | Low | `architecture.md` §2; PROJECT_BRIEF (traceability) | German-language driver omitted; German requirement not traceable to the brief at all | Resolved (docs) — `d98ab8f`; brief clarification with product owner still pending |
| F-04 | Low | `architecture.md` §5 | ffmpeg decode attributed to US-03; Increment 1 WAV path is in-memory Python, ffmpeg needed from Increment 3 | Resolved — `d98ab8f` |
| F-05 | Info | `architecture.md` §3 | "Frontend owned by another team" is an unsourced assumption | Resolved — `d98ab8f` |
| F-06 | Info | ADR-0002 | Links to `../FINDINGS.md`, deleted in commits `36cd9bc`/`a7a0760` (pre-existing; coincidentally re-satisfied while this file exists) | Open |

---

### F-01 — Decode position contradicts ADR-0002's memory argument (Medium)

**Where:** `architecture.md` §5 component flowchart (`decode → gate`) and §6
sequence diagram.

**Problem:** The diagrams place audio decode *before* the inference gate
(queue admission + per-worker semaphore). ADR-0002 §3's memory ceiling rests
on "with worker-level serialisation, only **N** decoded buffers are resident
at once." If up to `QUEUE_DEPTH` (32) admitted requests each decode before
waiting on the semaphore, up to 32 × ~172 MB PCM buffers could be resident —
exactly the R-02 exhaustion scenario the ADR closes.

**Root cause note:** ADR-0002 §1 is itself ambiguous ("hands the
decoded-audio work to a model worker" suggests the HTTP layer decodes), while
§3's arithmetic requires decode inside the serialised section. The
architecture document must resolve the ambiguity in the direction §3
requires.

**Recommendation:**
1. Move decode after slot acquisition in both diagrams (metadata probe for
   the `422` duration check stays before admission — it does not require full
   decode).
2. Clarify the ADR-0002 §1 wording so §1 and §3 cannot be read to conflict.
3. While editing, make the rejection-check ordering (size → duration →
   admission) explicit in ADR-0002; no source currently mandates an order and
   the architecture doc had to pick one.

---

### F-02 — Error contract incomplete (Medium)

**Where:** `architecture.md` §9, error-contract bullet.

**Problem:** Lists only `413` (too large), `422` (too long/unprocessable),
and `503` (overloaded). The canonical table in test-specification §3 also
defines `400` (`missing_file`, `bad_request`, `empty_file`) and `415`/`422`
(`unsupported_format`), plus the envelope shape
`{"error": {"code", "message"}}` and the requirement that a global exception
handler overrides FastAPI's default `{"detail": ...}` body. A frontend
developer using the architecture document as the contract reference would
miss half the negative paths.

**Recommendation:** Reproduce the full status/`code` table (or link
test-specification §3 as the single source of truth) and state the envelope
shape.

---

### F-03 — German-language driver omitted; brief traceability gap (Low)

**Where:** `architecture.md` §2 (drivers); PROJECT_BRIEF.md (upstream).

**Problem:** ADR-0001 lists German support as a decision driver, and the test
specification anchors its quality thresholds to German fixtures (TC-205,
TC-301, TC-303, TC-306). The architecture document never mentions language.

**Upstream observation (not an architecture-doc defect):** the German
requirement appears nowhere in PROJECT_BRIEF.md — ADR-0001 and the test spec
cite a requirement the brief does not state. **Action:** raise with the
product owner; either the brief is missing a requirement or the ADR/test spec
encode an assumption.

**Recommendation:** Add the German-language requirement to §2 of the
architecture document, citing ADR-0001 (and the brief, once clarified).

---

### F-04 — ffmpeg attribution overstated (Low)

**Where:** `architecture.md` §5, "Audio decode" component
("ffmpeg … US-03, US-08/09").

**Problem:** Increment 1's WAV path is plain in-memory Python (US-05:
`io.BytesIO`); the Dockerfile's own comment states ffmpeg is required "from
Increment 3 onward". Attributing ffmpeg decode to US-03 overstates it.

**Recommendation:** Label the component "WAV in-memory (US-03); ffmpeg
multi-format from Increment 3 (US-08/09)".

---

### F-05 — Unsourced assumption about the frontend (Info)

**Where:** `architecture.md` §3, context-diagram description of the
ClearVoice web application.

**Problem:** "Frontend owned by another team; consumes the transcription API"
is stated as fact; no source document says who owns the frontend.

**Recommendation:** Mark as an assumption or drop the ownership claim.

---

### F-06 — Dangling FINDINGS.md link in ADR-0002 (Info, pre-existing)

**Where:** ADR-0002, Context section: `[FINDINGS.md](../FINDINGS.md)`.

**Problem:** The referenced file was resolved and deleted (commits `36cd9bc`,
`a7a0760`), leaving a dead link. The existence of *this* file coincidentally
re-satisfies the path until it, too, is deleted.

**Recommendation:** Reword the ADR to cite the review by date/commit instead
of linking a transient file (e.g. "the v1.1 architectural review, resolved in
`116355a`").
