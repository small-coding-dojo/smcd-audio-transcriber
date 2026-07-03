"""Tests for environment-variable driven configuration defaults and overrides."""

from app.config import Settings


def test_settings_have_sensible_defaults():
    settings = Settings(_env_file=None)

    assert settings.whisper_model_size == "base"
    assert settings.device == "cpu"
    assert settings.max_concurrent_jobs == 2
    assert settings.max_upload_size_mb == 100
    assert settings.max_audio_duration_seconds == 1800


def test_settings_are_overridable_via_env(monkeypatch):
    monkeypatch.setenv("WHISPER_MODEL_SIZE", "small")
    monkeypatch.setenv("DEVICE", "cuda")
    monkeypatch.setenv("MAX_CONCURRENT_JOBS", "4")

    settings = Settings(_env_file=None)

    assert settings.whisper_model_size == "small"
    assert settings.device == "cuda"
    assert settings.max_concurrent_jobs == 4
