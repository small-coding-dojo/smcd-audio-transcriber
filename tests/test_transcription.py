"""Tests for the Phase 1 transcription service (app/transcription.py).

The `faster-whisper` model is mocked here - these are unit tests for the
segment/result mapping logic, not a real-model smoke test (a slower,
real-model-backed suite is planned for Phase 7).
"""

from types import SimpleNamespace

from app.transcription import transcribe_wav_bytes


class _FakeSegment:
    def __init__(self, start, end, text):
        self.start = start
        self.end = end
        self.text = text


class _FakeModel:
    def transcribe(self, audio, language=None, vad_filter=True):
        segments = [
            _FakeSegment(0.0, 1.5, " Hello there. "),
            _FakeSegment(1.5, 3.2, "How are you?"),
        ]
        info = SimpleNamespace(language="en", duration=3.2)
        return iter(segments), info


def test_transcribe_wav_bytes_maps_segments_and_defaults_speaker_to_none(monkeypatch):
    monkeypatch.setattr("app.transcription.get_whisper_model", lambda: _FakeModel())

    result = transcribe_wav_bytes(b"fake-wav-bytes")

    assert result.language == "en"
    assert result.duration_seconds == 3.2
    assert len(result.segments) == 2
    assert result.segments[0].start == 0.0
    assert result.segments[0].end == 1.5
    assert result.segments[0].text == "Hello there."
    assert result.segments[0].speaker is None
    assert result.segments[1].text == "How are you?"
