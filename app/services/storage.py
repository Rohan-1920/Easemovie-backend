import uuid
from pathlib import Path

from app.core.config import settings


MEDIA_ROOT = Path(settings.media_root)
IMAGES_DIR = MEDIA_ROOT / "images"
VIDEOS_DIR = MEDIA_ROOT / "videos"
AUDIO_DIR = MEDIA_ROOT / "audio"


def ensure_media_dirs() -> None:
    for folder in (IMAGES_DIR, VIDEOS_DIR, AUDIO_DIR):
        folder.mkdir(parents=True, exist_ok=True)


def new_image_path() -> Path:
    return IMAGES_DIR / f"{uuid.uuid4().hex}.png"


def new_video_path() -> Path:
    return VIDEOS_DIR / f"{uuid.uuid4().hex}.mp4"


def new_audio_path() -> Path:
    return AUDIO_DIR / f"{uuid.uuid4().hex}.mp3"
