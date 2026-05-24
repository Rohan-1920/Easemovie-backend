"""Log configuration status when the server starts."""

from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger("easemovie.config")

_PLACEHOLDER_MARKERS = ("paste_", "your_", "r8_your", "xxxx", "here", "example")


def is_valid_replicate_token(token: str) -> bool:
    """True when token is non-empty and not a template placeholder."""
    t = (token or "").strip()
    return bool(t) and not _looks_like_placeholder(t)


def _looks_like_placeholder(token: str) -> bool:
    t = token.strip().lower()
    if not t:
        return False
    if any(m in t for m in _PLACEHOLDER_MARKERS):
        return True
    # Real Replicate tokens usually start with r8_
    return not t.startswith("r8_")


def run_startup_checks() -> list[str]:
    warnings: list[str] = []

    image_tok = settings.image_token()
    if not image_tok:
        warnings.append("IMAGE_REPLICATE_API_TOKEN (or REPLICATE_API_TOKEN) is missing — images will use fallback PNG.")
    elif _looks_like_placeholder(image_tok):
        warnings.append(
            "IMAGE_REPLICATE_API_TOKEN looks like a placeholder — replace with your real r8_... token from Replicate."
        )
    else:
        logger.info("Image model ready: %s", settings.image_model)

    video_tok = settings.video_token()
    if not video_tok:
        warnings.append("VIDEO_REPLICATE_API_TOKEN (or REPLICATE_API_TOKEN) is missing — video will use slideshow fallback.")
    elif _looks_like_placeholder(video_tok):
        warnings.append(
            "VIDEO_REPLICATE_API_TOKEN looks like a placeholder — replace with your real r8_... token from Replicate."
        )
    else:
        logger.info("Video model ready: %s", settings.video_model)

    if not (settings.public_base_url or "").strip():
        warnings.append(
            "PUBLIC_BASE_URL is not set. Set it to your PC LAN URL (e.g. http://192.168.1.20:8000) "
            "so Replicate can load scene images for video; otherwise files are uploaded to Replicate automatically."
        )
    else:
        logger.info("PUBLIC_BASE_URL: %s", settings.public_base_url.strip())

    for msg in warnings:
        logger.warning(msg)

    return warnings
