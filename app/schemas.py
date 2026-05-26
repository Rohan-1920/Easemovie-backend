from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SegmentRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "text": "A young girl named Mira finds a glowing lantern in an old forest. She follows fireflies to a hidden lake. She makes a wish and walks home at dawn with eternal light."
                }
            ]
        }
    )

    text: str = Field(..., min_length=1)


class SceneDto(BaseModel):
    index: int
    text: str
    mood: str
    camera: str
    voice: str = Field(
        default="auto",
        description="Recommended voice id (ElevenLabs) or Edge TTS name for this scene.",
    )
    voice_name: str = Field(default="", description="Human-readable voice label.")


class SegmentResponse(BaseModel):
    scenes: list[SceneDto]


class ImageResponse(BaseModel):
    image_path: str


class VideoResponse(BaseModel):
    video_url: str = ""
    source: str = "pending"
    voice: str | None = Field(default=None, description="Primary narration voice id when voice was used.")
    voice_name: str | None = Field(default=None, description="Human-readable narration voice name.")
    provider: str | None = Field(default=None, description="elevenlabs or edge when narration was synthesized.")
    job_id: str | None = Field(
        default=None,
        description="Present when generation runs in background; poll GET /jobs/{job_id}.",
    )


class JobStatusResponse(BaseModel):
    job_id: str
    kind: str
    status: str
    progress: float
    message: str
    result: dict | None = None
    error: str | None = None
    created_at: float
    updated_at: float


class VideoGenerateRequest(BaseModel):
    """Text-only slideshow (dev/fallback). For paid AI video use POST /generate_video_from_images with image_url."""

    text: str = Field(
        ...,
        min_length=1,
        description="Scene or story description for the video.",
        json_schema_extra={"examples": ["Mira walks through a glowing forest at sunset, fireflies floating around her"]},
    )
    style: str = Field(
        ...,
        min_length=1,
        description="Visual style for the video.",
        json_schema_extra={"examples": ["Pixar-style 3D animation, cinematic lighting, ultra detailed"]},
    )
    emotion: str = Field(
        ...,
        min_length=1,
        description="Mood / emotion of the scene.",
        json_schema_extra={"examples": ["curious, magical, warm"]},
    )
    seconds_per_scene: float = Field(
        default=3.0,
        gt=0,
        le=60,
        description="Duration per scene for text slideshow fallback.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "text": "Mira walks through a glowing forest at sunset, fireflies floating around her, cinematic wide shot",
                    "style": "Pixar-style 3D animation, cinematic lighting, ultra detailed",
                    "emotion": "curious, magical, warm",
                    "seconds_per_scene": 3.0,
                }
            ]
        }
    )


class VideoFromImageRequest(BaseModel):
    """Scene image(s) → SVD animated clip(s). Use image_urls for multi-scene."""

    image_url: str | None = Field(
        default=None,
        min_length=1,
        description="Single scene image URL from POST /generate_image.",
    )
    image_urls: list[str] | None = Field(
        default=None,
        description="Multiple scene image URLs (multi-scene SVD when 2+ URLs).",
    )
    text: str = Field(
        ...,
        min_length=1,
        description="Scene / motion description for the video.",
    )
    style: str = Field(
        ...,
        min_length=1,
        description="Visual style (used for slideshow fallback).",
    )
    emotion: str = Field(
        ...,
        min_length=1,
        description="Mood / emotion of the scene.",
    )
    scene_texts: list[str] | None = Field(
        default=None,
        description="Optional per-scene motion prompts (same order as image_urls).",
    )
    scene_emotions: list[str] | None = Field(
        default=None,
        description="Optional per-scene moods for motion/voice hints.",
    )
    seconds_per_scene: float = Field(
        default=5.0,
        gt=0,
        le=60,
        description="Clip length for slideshow fallback when multiple images are used.",
    )

    @model_validator(mode="after")
    def require_image(self) -> VideoFromImageRequest:
        single = (self.image_url or "").strip()
        multi = [u.strip() for u in (self.image_urls or []) if u and u.strip()]
        if not single and not multi:
            raise ValueError("Provide image_url or image_urls.")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "image_url": "http://192.168.1.20:8000/media/images/28ea21ae93b240d49428c08c24067d59.png",
                    "text": "Mira walks slowly through the glowing forest, fireflies swirl around her, gentle camera push-in",
                    "style": "Pixar-style 3D animation, cinematic lighting, ultra detailed",
                    "emotion": "curious, magical, warm",
                    "seconds_per_scene": 5.0,
                }
            ]
        }
    )


class VoiceRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "text": "In a forest at dusk, Mira found a lantern that would never go out. She followed the fireflies to a lake of stars and carried the light home forever.",
                    "voice": "auto",
                }
            ]
        }
    )

    text: str = Field(..., min_length=1)
    voice: str = Field(
        default="auto",
        description='Use "auto" for mood/story-based voice, or a name like Adam/Rachel, ElevenLabs voice id, or Edge name.',
    )
    story_context: str | None = Field(
        default=None,
        description="Optional full story text to improve genre-based voice selection.",
    )


class VoiceResponse(BaseModel):
    audio_url: str
    voice: str = Field(description="Voice id used for synthesis.")
    voice_name: str = Field(default="", description="Human-readable voice name.")
    mood: str = Field(default="", description="Detected scene mood.")
    story_genre: str = Field(default="", description="Detected story genre.")
    provider: str = Field(default="", description="elevenlabs or edge")


class ComposeFilmRequest(BaseModel):
    """
    Multi-scene film: each image_url is animated with SVD, clips are joined, optional narration mixed in.
    Use scene_narrations + scene_moods from POST /segment for voice and motion per scene.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "image_urls": [
                        "http://192.168.1.20:8000/media/images/28ea21ae93b240d49428c08c24067d59.png",
                    ],
                    "seconds_per_scene": 4.0,
                    "narration_text": "Mira found a magical lantern in the forest.",
                    "voice": "auto",
                    "user_id": "user123",
                    "title": "Forest Tale",
                    "style": "Pixar-style 3D",
                    "save_project": True,
                }
            ]
        }
    )

    image_urls: list[str] = Field(..., min_length=1)
    seconds_per_scene: float = Field(default=3.0, gt=0, le=60)
    narration_text: str | None = None
    scene_narrations: list[str] | None = None
    scene_moods: list[str] | None = Field(
        default=None,
        description="Optional per-scene moods from /segment; improves auto voice selection.",
    )
    voice: str = Field(
        default="auto",
        description='Use "auto" for mood/story-based voice, or explicit voice name/id.',
    )
    story_context: str | None = Field(
        default=None,
        description="Optional full story text for consistent genre-based narration.",
    )

    # Optional project metadata to save generated content into Firestore.
    user_id: str | None = None
    title: str | None = None
    style: str | None = None
    thumbnail_url: str | None = None
    scenes: list[str] | None = None
    save_project: bool = Field(default=False)

    @model_validator(mode="after")
    def narration_exclusive(self) -> ComposeFilmRequest:
        has_text = bool(self.narration_text and self.narration_text.strip())
        has_scenes = bool(self.scene_narrations)
        if has_text and has_scenes:
            raise ValueError("Use either narration_text or scene_narrations, not both.")
        if self.scene_moods and self.scene_narrations:
            if len(self.scene_moods) != len(self.scene_narrations):
                raise ValueError("scene_moods must have the same length as scene_narrations.")
        if self.scene_moods and not self.scene_narrations:
            if len(self.scene_moods) != len(self.image_urls):
                raise ValueError("scene_moods must have the same length as image_urls.")
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
