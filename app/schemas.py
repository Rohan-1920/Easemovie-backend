from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class SegmentRequest(BaseModel):
    text: str = Field(..., min_length=1)


class SceneDto(BaseModel):
    index: int
    text: str
    mood: str
    camera: str


class SegmentResponse(BaseModel):
    scenes: list[SceneDto]


class ImageResponse(BaseModel):
    image_path: str


class VideoRequest(BaseModel):
    scenes: list[str]
    style: str


class VideoResponse(BaseModel):
    video_url: str


class VideoFromImagesRequest(BaseModel):
    """Build a slideshow video from scene image URLs (images must already exist)."""

    image_urls: list[str] = Field(..., min_length=1)
    seconds_per_scene: float = Field(default=3.0, gt=0, le=60)


class VoiceRequest(BaseModel):
    text: str = Field(..., min_length=1)
    voice: str = Field(default="en-US-JennyNeural")


class VoiceResponse(BaseModel):
    audio_url: str


class ComposeFilmRequest(BaseModel):
    """
    Short film: image slideshow plus optional narration (single block or per-scene lines).
    Do not send both narration modes at once.
    """

    image_urls: list[str] = Field(..., min_length=1)
    seconds_per_scene: float = Field(default=3.0, gt=0, le=60)
    narration_text: str | None = None
    scene_narrations: list[str] | None = None
    voice: str = Field(default="en-US-JennyNeural")

    @model_validator(mode="after")
    def narration_exclusive(self) -> ComposeFilmRequest:
        has_text = bool(self.narration_text and self.narration_text.strip())
        has_scenes = bool(self.scene_narrations)
        if has_text and has_scenes:
            raise ValueError("Use either narration_text or scene_narrations, not both.")
        return self


class ProjectCreate(BaseModel):
    user_id: str
    title: str
    style: str
    video_url: str
    thumbnail_url: str = ""
    scenes: list[str] = Field(default_factory=list)


class ProjectOut(ProjectCreate):
    id: str
    created_at: str
