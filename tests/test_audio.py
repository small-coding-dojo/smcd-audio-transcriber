"""Tests for Phase 1 audio ingestion/normalization (app/audio.py).

`ffmpeg`/`ffprobe` subprocess calls are monkeypatched at the module-function
level so these tests run without the actual binaries on PATH (see README for
real-binary smoke-testing notes).
"""

import os

import pytest

from app.audio import (
    AudioTooLongError,
    CorruptAudioError,
    UnsupportedAudioFormatError,
    normalize_audio,
    validate_extension_and_content_type,
)


def test_validate_accepts_known_extension():
    validate_extension_and_content_type("recording.wav", "audio/wav")


def test_validate_accepts_known_content_type_with_unhelpful_extension():
    validate_extension_and_content_type("blob", "audio/mpeg")


def test_validate_rejects_unsupported_format():
    with pytest.raises(UnsupportedAudioFormatError):
        validate_extension_and_content_type("document.pdf", "application/pdf")


def test_validate_rejects_missing_filename_and_content_type():
    with pytest.raises(UnsupportedAudioFormatError):
        validate_extension_and_content_type(None, None)


def test_normalize_audio_rejects_empty_bytes():
    with pytest.raises(CorruptAudioError):
        normalize_audio(b"", max_duration_seconds=30)


def test_normalize_audio_cleans_up_temp_file_on_success(monkeypatch):
    captured_paths = []

    def fake_probe(path):
        captured_paths.append(path)
        return 2.0

    def fake_ffmpeg(path):
        captured_paths.append(path)
        return b"RIFF....WAVEfmt "

    monkeypatch.setattr("app.audio._probe_duration_seconds", fake_probe)
    monkeypatch.setattr("app.audio._run_ffmpeg_to_wav", fake_ffmpeg)

    result = normalize_audio(b"raw-bytes", max_duration_seconds=30)

    assert result.duration_seconds == 2.0
    assert result.wav_bytes == b"RIFF....WAVEfmt "
    assert len(captured_paths) == 2
    assert not os.path.exists(captured_paths[0])


def test_normalize_audio_cleans_up_temp_file_on_ffmpeg_error(monkeypatch):
    tmp_path_holder: dict[str, str] = {}

    def fake_probe(path):
        tmp_path_holder["path"] = path
        return 2.0

    def fake_ffmpeg(path):
        raise CorruptAudioError("boom")

    monkeypatch.setattr("app.audio._probe_duration_seconds", fake_probe)
    monkeypatch.setattr("app.audio._run_ffmpeg_to_wav", fake_ffmpeg)

    with pytest.raises(CorruptAudioError):
        normalize_audio(b"raw-bytes", max_duration_seconds=30)

    assert not os.path.exists(tmp_path_holder["path"])


def test_normalize_audio_rejects_too_long_duration(monkeypatch):
    monkeypatch.setattr("app.audio._probe_duration_seconds", lambda path: 999.0)

    with pytest.raises(AudioTooLongError):
        normalize_audio(b"raw-bytes", max_duration_seconds=30)


def test_normalize_audio_rejects_zero_duration(monkeypatch):
    monkeypatch.setattr("app.audio._probe_duration_seconds", lambda path: 0.0)

    with pytest.raises(CorruptAudioError):
        normalize_audio(b"raw-bytes", max_duration_seconds=30)
