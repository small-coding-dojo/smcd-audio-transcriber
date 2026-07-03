"""Internal transcript data model and API response schema.

These Pydantic models double as both the internal representation passed
between the audio ingestion / transcription services (Phase 1 onward) and the
schema serialized in the API response - Phase 3 wires them into the
`POST /transcribe` endpoint's `response_model`.
"""

from pydantic import BaseModel, Field


class TranscriptSegment(BaseModel):
    """A single timestamped chunk of transcribed speech."""

    start: float = Field(..., ge=0, description="Segment start time in seconds from the start of the audio.")
    end: float = Field(..., ge=0, description="Segment end time in seconds from the start of the audio.")
    text: str = Field(..., description="Transcribed text for this segment.")
    speaker: str | None = Field(
        default=None,
        description=(
            "Speaker label, e.g. 'Speaker 1'. Always None until Phase 2 (diarisation) is "
            "implemented."
        ),
    )


class TranscriptionResult(BaseModel):
    """Full transcription result for one audio upload."""

    segments: list[TranscriptSegment] = Field(default_factory=list)
    language: str = Field(..., description="Detected (or forced) ISO-639-1 language code.")
    duration_seconds: float = Field(..., ge=0, description="Total audio duration in seconds.")
