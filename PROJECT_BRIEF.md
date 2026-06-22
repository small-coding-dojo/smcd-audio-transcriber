# ClearVoice — Audio Transcriber Service

## Project Brief

**From:** Product Owner, ClearVoice
**To:** Engineering
**Priority:** High

---

## Overview

ClearVoice is building a web application that allows users to upload an audio recording and receive a text transcript — with timestamps and speaker identification.

We need you to develop the **Audio Transcriber Service** — a service exposing a single HTTP endpoint that accepts an audio file and returns a structured transcript.

## Requirements

### Core Functionality

1. The service must accept an uploaded audio file and return a transcript of the spoken content.
2. The transcript should include **timestamps** — the user should be able to see when each segment of speech occurs.
3. The service should attempt **speaker diarisation** — distinguishing between different speakers in the recording and labelling them (e.g., Speaker 1, Speaker 2).
4. The service should handle common audio formats.

### Privacy

ClearVoice takes user privacy seriously.

- Uploaded audio files **must never be stored** beyond what is necessary to process the request.
- No uploaded audio data should be written to disk, logged, or retained after the response is sent.
- Transcript content must not be logged or stored after the response is sent.

### Performance

- The service should respond **within a reasonable time** relative to the length of the audio.
- The service should be capable of handling **multiple concurrent requests** without degrading.

### Quality

- The transcript should be **accurate enough to be useful** without manual correction for most clear recordings.
- The service should handle edge cases **gracefully** (e.g., silence, background noise, very long recordings, unsupported format).
- The response format should be **structured and easy to consume** by a frontend application.

## Evaluation Criteria

Your submission will be evaluated on:

- **Robustness** — Does it handle edge cases and unexpected input well?
- **Latency** — How fast does it respond relative to audio length?
- **Performance under load** — How does it behave with concurrent users?
- **Resource consumption** — Is it efficient with memory and CPU?
- **Code quality** — Documentation, readability, maintainability, and near-production readiness.

## Deliverables

- A working service with a single endpoint for audio transcription.
- A README documenting how to build, run, and test the service.
- Any configuration or setup scripts necessary.

## Extra Credit

If time permits: extend the service to accept a **live microphone stream** and return transcript segments in real time via WebSocket or server-sent events.

---

*Every word matters — make sure we catch them all.*
