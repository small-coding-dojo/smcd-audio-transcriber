"""Core transcription service: wraps `faster-whisper` to produce timestamped
transcript segments from normalized (16kHz mono WAV) audio bytes.

Model size default and language-detection behavior: see README
"Transcription model" section for the accuracy/latency rationale.

`faster-whisper` is an optional ("ml" extra) dependency - importing it lazily
inside `get_whisper_model` keeps this module importable (and unit-testable)
without the heavy ML dependencies installed.
"""

import io
import logging
from functools import lru_cache

from app.config import get_settings
from app.models import TranscriptSegment, TranscriptionResult

logger = logging.getLogger("app")


@lru_cache
def get_whisper_model():
    """Load and cache the `faster-whisper` model instance for this process.

    Loading a model is expensive (disk I/O + weight deserialization), so it
    happens once per process and is shared across requests rather than
    reloaded per request (see Phase 5 for concurrency/throughput handling).
    """
    from faster_whisper import WhisperModel  # Lazy import: optional "ml" dependency.

    settings = get_settings()
    logger.info("whisper_model_loading", extra={"event": "whisper_model_loading"})
    return WhisperModel(
        settings.whisper_model_size,
        device=settings.device,
        compute_type=settings.compute_type,
        download_root=settings.model_cache_dir,
    )


def transcribe_wav_bytes(wav_bytes: bytes) -> TranscriptionResult:
    """Transcribe normalized WAV bytes into timestamped segments.

    Speaker labels are not populated here - Phase 2 adds diarisation - so
    every segment's `speaker` field is left as `None`.
    """
    settings = get_settings()
    model = get_whisper_model()

    segments_iter, info = model.transcribe(
        io.BytesIO(wav_bytes),
        language=settings.whisper_language,
        vad_filter=True,
    )

    segments = [
        TranscriptSegment(start=segment.start, end=segment.end, text=segment.text.strip(), speaker=None)
        for segment in segments_iter
    ]

    return TranscriptionResult(
        segments=segments,
        language=info.language,
        duration_seconds=info.duration,
    )
