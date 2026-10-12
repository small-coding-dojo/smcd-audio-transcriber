# API contract (UI ↔ Audio Transcriber Service) — proposal

Asynchronous, anonymous (no auth yet). Audio and transcripts must never be persisted or logged server-side
beyond processing; a finished result may be fetched until deleted or expired.

| Call | Purpose | Success |
|---|---|---|
| `POST /v1/jobs` (multipart, field `audio`) | Submit audio | `202 {"id": "<uuid>"}` |
| `GET /v1/jobs/:id` | Poll (UI polls every 1 s) | `200 JobState` |
| `DELETE /v1/jobs/:id` | Cancel and discard | `204` |

`JobState`:
```json
{"status": "queued"}
{"status": "processing", "progress": 0.42}          // progress optional, 0..1
{"status": "done", "result": {
  "duration": 312.4, "language": "en", "speakers": ["Speaker 1", "Speaker 2"],
  "segments": [{"start": 0.0, "end": 4.2, "speaker": "Speaker 1", "text": "…"}]}}
{"status": "failed", "error": {"code": "no_speech", "message": "…"}}
```
`speaker` is `null` and `speakers` is `[]` when diarisation is unavailable.
Error codes: `unsupported_format`, `too_large`, `no_speech`, `timeout`, `internal`.
Request-level errors (4xx/5xx) use `{"error": {"code", "message"}}`.
