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

    model_config = {"json_schema_extra": {"examples": [{"scenes": ["Scene 1 text", "Scene 2 text"], "style": "Cinematic"}]}}


class VideoResponse(BaseModel):
    video_url: str


class VideoFromImagesRequest(BaseModel):
    """Build a slideshow video from scene image URLs (images must already exist)."""

    image_urls: list[str] = Field(..., min_length=1)
    seconds_per_scene: float = Field(default=3.0, gt=0, le=60)

    model_config = {"json_schema_extra": {"examples": [{"image_urls": ["http://127.0.0.1:8000/media/images/scene1.png", "http://127.0.0.1:8000/media/images/scene2.png"], "seconds_per_scene": 3.0}]}}


class VoiceRequest(BaseModel):
    text: str = Field(..., min_length=1)
    voice: str = Field(default="en-US-JennyNeural")

    model_config = {"json_schema_extra": {"examples": [{"text": "Hello world", "voice": "en-US-AriaRUS"}]}}


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

    # Optional project metadata to save generated content into Firestore.
    user_id: str | None = None
    title: str | None = None
    style: str | None = None
    thumbnail_url: str | None = None
    scenes: list[str] | None = None
    save_project: bool = Field(default=False)

    model_config = {"json_schema_extra": {"examples": [
        {
            "image_urls": ["http://127.0.0.1:8000/media/images/scene1.png", "http://127.0.0.1:8000/media/images/scene2.png"],
            "seconds_per_scene": 4.0,
            "narration_text": "Once upon a time...",
            "voice": "en-US-AriaRUS",
            "user_id": "user123",
            "title": "Fairy Tale Adventure",
            "style": "Whimsical 3D",
            "thumbnail_url": "http://127.0.0.1:8000/media/images/thumb.png",
            "scenes": ["Scene one text", "Scene two text"],
            "save_project": True
        },
        {
            "image_urls": ["http://127.0.0.1:8000/media/images/scene1.png", "http://127.0.0.1:8000/media/images/scene2.png"],
            "seconds_per_scene": 4.0,
            "scene_narrations": ["Narration for scene 1", "Narration for scene 2"],
            "voice": "en-US-AriaRUS",
            "user_id": "user123",
            "title": "Fairy Tale Adventure",
            "style": "Whimsical 3D",
            "thumbnail_url": "http://127.0.0.1:8000/media/images/thumb.png",
            "scenes": ["Scene one text", "Scene two text"],
            "save_project": True
        }
    ]}}

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


class UserCreate(BaseModel):
    email: str = Field(..., min_length=1)
    password: str = Field(..., min_length=6)
    name: str | None = None


class UserOut(BaseModel):
    id: str
    email: str
    name: str | None = None
    created_at: str


class SignInRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
