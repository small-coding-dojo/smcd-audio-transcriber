---
description: "Implement Phase 0 (Scaffolding & Project Setup) of the Audio Transcriber Service"
name: "Phase 0: Scaffolding & Project Setup"
agent: "agent"
---
Read [PROJECT_BRIEF.md](../../PROJECT_BRIEF.md) and the high-level plan in [plan-audioTranscriberService.prompt.md](./plan-audioTranscriberService.prompt.md) for full context, then implement **Phase 0: Scaffolding & Project Setup** of the Audio Transcriber Service.

**Confirmed decisions to follow:**
- Language/framework: Python + FastAPI.
- Transcription engine: local model via `faster-whisper` (not a cloud API).
- Diarisation: WhisperX (added in a later phase, but dependencies should be scaffolded now).

**Tasks:**
- Initialize the Python project (`pyproject.toml` or `requirements.txt` + virtual environment) with a clear repo structure (`app/`, `tests/`, `README.md`).
- Set up the FastAPI app skeleton with a health-check endpoint.
- Add a config module driven by environment variables for: model size, device (CPU/GPU), concurrency limits, and max upload size/duration.
- Set up dependency management for the heavy ML dependencies (`faster-whisper`, `whisperx`, `pyannote.audio`, `torch`/`torchaudio`, `ffmpeg-python` or subprocess-based `ffmpeg`).
- Decide and document the model download/caching strategy (pre-baked into the container image at build time vs first-run download) so no runtime network calls are required for transcription requests.
- Set up structured logging with a strict rule enforced in code: log only metadata (request id, duration, status, file size/duration) and never audio content, transcript text, or file paths containing user data.
- Add a Dockerfile (or document the chosen deployment target) if a decision has been made; otherwise leave a clearly marked `TODO`/open question in the README.

**Open questions to flag (do not block implementation, note them in the README instead):**
- Docker vs bare-metal deployment target.
- GPU vs CPU-only assumption (affects default model size and latency expectations).

**Definition of done:**
- Project runs locally (`uvicorn` or equivalent) and the health-check endpoint responds.
- Config values are all environment-variable driven with sensible defaults.
- No ML inference code yet, only scaffolding and dependency wiring.
- README documents how to install and run the skeleton service.
