"""Phase 1 core transcription pipeline: ties audio ingestion together with
faster-whisper transcription into a single internal entry point.

Not yet exposed via the API (that's Phase 3) - this is the internal
function/service the future `POST /transcribe` endpoint will call.
"""

import logging

from app.audio import normalize_audio, validate_extension_and_content_type
from app.config import get_settings
from app.models import TranscriptionResult
from app.transcription import transcribe_wav_bytes

logger = logging.getLogger("app")


def transcribe_audio_upload(
    raw_bytes: bytes,
    *,
    filename: str | None,
    content_type: str | None,
) -> TranscriptionResult:
    """Validate, normalize, and transcribe a raw audio upload end-to-end.

    Raises `app.audio.UnsupportedAudioFormatError`, `CorruptAudioError`, or
    `AudioTooLongError` for invalid input. The future API layer (Phase 3) is
    expected to translate these into appropriate 4xx error responses.
    """
    settings = get_settings()

    validate_extension_and_content_type(filename, content_type)

    normalized = normalize_audio(raw_bytes, max_duration_seconds=settings.max_audio_duration_seconds)

    logger.info(
        "transcription_started",
        extra={"event": "transcription_started", "audio_duration_seconds": normalized.duration_seconds},
    )
    result = transcribe_wav_bytes(normalized.wav_bytes)
    logger.info(
        "transcription_completed",
        extra={"event": "transcription_completed", "audio_duration_seconds": result.duration_seconds},
    )
    return result
