"""Tests for the Phase 1 end-to-end internal transcription pipeline
(app/pipeline.py) - the internal service the future API layer (Phase 3)
will call.
"""

import pytest

from app.audio import NormalizedAudio, UnsupportedAudioFormatError
from app.models import TranscriptionResult
from app.pipeline import transcribe_audio_upload


def test_transcribe_audio_upload_rejects_unsupported_format():
    with pytest.raises(UnsupportedAudioFormatError):
        transcribe_audio_upload(b"data", filename="notes.pdf", content_type="application/pdf")


def test_transcribe_audio_upload_normalizes_then_transcribes(monkeypatch):
    fake_normalized = NormalizedAudio(wav_bytes=b"wav-bytes", duration_seconds=5.0)
    fake_result = TranscriptionResult(segments=[], language="en", duration_seconds=5.0)
    received = {}

    def fake_normalize_audio(raw_bytes, *, max_duration_seconds):
        received["raw_bytes"] = raw_bytes
        received["max_duration_seconds"] = max_duration_seconds
        return fake_normalized

    def fake_transcribe_wav_bytes(wav_bytes):
        received["wav_bytes"] = wav_bytes
        return fake_result

    monkeypatch.setattr("app.pipeline.normalize_audio", fake_normalize_audio)
    monkeypatch.setattr("app.pipeline.transcribe_wav_bytes", fake_transcribe_wav_bytes)

    result = transcribe_audio_upload(b"raw-bytes", filename="clip.wav", content_type="audio/wav")

    assert result is fake_result
    assert received["raw_bytes"] == b"raw-bytes"
    assert received["wav_bytes"] == b"wav-bytes"
