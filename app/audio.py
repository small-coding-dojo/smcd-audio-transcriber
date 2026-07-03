"""Audio ingestion: format/duration validation and normalization to 16kHz
mono WAV via `ffmpeg`.

Privacy: the uploaded audio is written to a single OS temp file only because
`ffmpeg`/`ffprobe` need a seekable input path for many containers (e.g.
mp4/m4a don't reliably decode from a stdin pipe). That temp file is always
deleted in a `finally` block - even if validation, probing, or conversion
raises - so no uploaded audio ever outlives a single request. The normalized
output (WAV bytes) is kept in memory and never written to disk.
"""

import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("app")

TARGET_SAMPLE_RATE = 16000
TARGET_CHANNELS = 1

# Early, cheap rejection layer (see also Phase 6 for deeper corrupt-file
# handling). The authoritative check is still whether ffprobe/ffmpeg can
# actually decode the file - this just avoids invoking them for obviously
# unsupported uploads (e.g. a PDF).
_ALLOWED_EXTENSIONS = {
    ".wav",
    ".mp3",
    ".m4a",
    ".mp4",
    ".flac",
    ".ogg",
    ".oga",
    ".webm",
    ".aac",
    ".wma",
    ".opus",
}
_ALLOWED_CONTENT_TYPE_PREFIXES = ("audio/",)
_ALLOWED_CONTENT_TYPES = {"video/webm", "video/mp4", "application/octet-stream"}


class UnsupportedAudioFormatError(ValueError):
    """Raised when the uploaded file extension/content-type isn't supported."""


class CorruptAudioError(ValueError):
    """Raised when ffmpeg/ffprobe cannot read or decode the uploaded file."""


class AudioTooLongError(ValueError):
    """Raised when the probed audio duration exceeds the configured maximum."""


@dataclass(frozen=True)
class NormalizedAudio:
    """In-memory 16kHz mono WAV bytes plus the probed source duration."""

    wav_bytes: bytes
    duration_seconds: float


def validate_extension_and_content_type(filename: str | None, content_type: str | None) -> None:
    """Reject obviously unsupported uploads early, before invoking ffmpeg."""
    extension = Path(filename).suffix.lower() if filename else ""
    is_allowed_content_type = bool(content_type) and (
        content_type.startswith(_ALLOWED_CONTENT_TYPE_PREFIXES) or content_type in _ALLOWED_CONTENT_TYPES
    )

    if extension not in _ALLOWED_EXTENSIONS and not is_allowed_content_type:
        raise UnsupportedAudioFormatError(
            f"Unsupported file extension {extension!r} / content-type {content_type!r}. "
            f"Supported extensions: {sorted(_ALLOWED_EXTENSIONS)}."
        )


def _probe_duration_seconds(path: str) -> float:
    """Return the audio duration in seconds via `ffprobe`."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("ffprobe is not installed or not on PATH.") from exc

    if result.returncode != 0 or not result.stdout.strip():
        raise CorruptAudioError("Unable to read audio duration; file may be corrupt or unreadable.")

    try:
        return float(result.stdout.strip())
    except ValueError as exc:
        raise CorruptAudioError("Unable to parse probed audio duration.") from exc


def _run_ffmpeg_to_wav(input_path: str) -> bytes:
    """Convert the file at `input_path` to 16kHz mono WAV bytes via `ffmpeg`."""
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                input_path,
                "-ar",
                str(TARGET_SAMPLE_RATE),
                "-ac",
                str(TARGET_CHANNELS),
                "-f",
                "wav",
                "pipe:1",
            ],
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg is not installed or not on PATH.") from exc

    if result.returncode != 0 or not result.stdout:
        raise CorruptAudioError("ffmpeg could not decode/convert the uploaded audio file.")

    return result.stdout


def normalize_audio(raw_bytes: bytes, *, max_duration_seconds: float) -> NormalizedAudio:
    """Validate duration and convert raw audio bytes to 16kHz mono WAV bytes.

    The only disk I/O is a single temp file holding the raw upload, which is
    guaranteed to be removed before this function returns or raises.
    """
    if not raw_bytes:
        raise CorruptAudioError("Uploaded file is empty.")

    fd, tmp_path = tempfile.mkstemp(prefix="clearvoice-upload-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as tmp_file:
            tmp_file.write(raw_bytes)

        duration_seconds = _probe_duration_seconds(tmp_path)
        if duration_seconds <= 0:
            raise CorruptAudioError("Audio file has no decodable duration.")
        if duration_seconds > max_duration_seconds:
            raise AudioTooLongError(
                f"Audio duration {duration_seconds:.1f}s exceeds the maximum of "
                f"{max_duration_seconds:.0f}s."
            )

        wav_bytes = _run_ffmpeg_to_wav(tmp_path)
        return NormalizedAudio(wav_bytes=wav_bytes, duration_seconds=duration_seconds)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            logger.warning("temp_file_cleanup_failed", extra={"event": "temp_cleanup_failed"})
