"""Video generation — AI video model with slideshow fallback."""

from app.providers.video_model import generate_video_file, is_ai_video_configured
from app.services.video_slideshow import generate_slideshow_from_scene_text

__all__ = [
    "generate_video_file",
    "generate_slideshow_from_scene_text",
    "is_ai_video_configured",
]
