"""Application configuration.

All settings are environment-variable driven with sensible defaults so the
service is configurable without code changes across dev/CI/prod. Values can
also be supplied via a local `.env` file (see `.env.example`).
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ClearVoice Audio Transcriber Service"
    log_level: str = Field(default="INFO", description="Python logging level, e.g. DEBUG/INFO/WARNING")

    # --- Transcription model configuration (consumed from Phase 1 onward) ---
    whisper_model_size: Literal["tiny", "base", "small", "medium", "large-v3"] = Field(
        default="base",
        description="faster-whisper / WhisperX model size. Bigger = more accurate, slower, more memory.",
    )
    device: Literal["cpu", "cuda"] = Field(
        default="cpu",
        description="Inference device. Defaults to CPU-only; set to 'cuda' if a GPU is available.",
    )
    compute_type: str = Field(
        default="int8",
        description=(
            "faster-whisper compute type, e.g. 'int8' (CPU-friendly), 'float16' or "
            "'int8_float16' (typical for GPU)."
        ),
    )

    # --- Concurrency (consumed from Phase 5 onward) ---
    max_concurrent_jobs: int = Field(
        default=2, ge=1, description="Max number of transcription/diarisation jobs running at once."
    )

    # --- Upload limits (consumed from Phase 1/3 onward) ---
    max_upload_size_mb: int = Field(default=100, ge=1, description="Max accepted upload size in megabytes.")
    max_audio_duration_seconds: int = Field(
        default=1800, ge=1, description="Max accepted audio duration in seconds (default: 30 minutes)."
    )

    # --- Diarisation (consumed from Phase 2 onward) ---
    huggingface_token: str | None = Field(
        default=None,
        description=(
            "HuggingFace access token required by pyannote.audio's pretrained diarisation "
            "pipelines. Reserved for Phase 2; not used yet. Never commit a real value - set via "
            "environment/secret store only."
        ),
    )

    # --- Model download / caching strategy (see README) ---
    model_cache_dir: str = Field(
        default="/models",
        description=(
            "Directory models are loaded from. Intended to be pre-baked into the container image "
            "at build time so no runtime network calls are required to serve a transcription request."
        ),
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (env is read once per process)."""
    return Settings()
