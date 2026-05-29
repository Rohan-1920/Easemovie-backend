"""ElevenLabs text-to-speech API client."""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger("easemovie.elevenlabs")

ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
ELEVENLABS_USER_URL = "https://api.elevenlabs.io/v1/user"


def _api_key() -> str:
    return (settings.elevenlabs_api_key or "").strip()


async def verify_api_key() -> tuple[bool, str]:
    """Call ElevenLabs /v1/user — returns (ok, error_message)."""
    api_key = _api_key()
    if not api_key:
        return False, "ELEVENLABS_API_KEY is not set."

    timeout = httpx.Timeout(connect=15.0, read=30.0, write=15.0, pool=15.0)
    headers = {"xi-api-key": api_key}
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(ELEVENLABS_USER_URL, headers=headers)

    if response.status_code == 401:
        return False, (
            "ElevenLabs API key is invalid (401). Use a new key from "
            "https://elevenlabs.io/app/settings/api-keys with Text to Speech + Voices Read + Models Read."
        )
    if response.status_code >= 400:
        return False, f"ElevenLabs key check failed ({response.status_code}): {response.text[:200]}"
    return True, ""


async def synthesize_speech_mp3(text: str, voice_id: str) -> bytes:
    api_key = _api_key()
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY is not set.")

    payload = {
        "text": text,
        "model_id": settings.elevenlabs_model,
        "voice_settings": {
            "stability": settings.elevenlabs_stability,
            "similarity_boost": settings.elevenlabs_similarity_boost,
            "style": settings.elevenlabs_style,
            "use_speaker_boost": settings.elevenlabs_use_speaker_boost,
        },
    }
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }

    timeout = httpx.Timeout(connect=30.0, read=120.0, write=30.0, pool=30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            ELEVENLABS_TTS_URL.format(voice_id=voice_id),
            headers=headers,
            json=payload,
        )

    if response.status_code == 401:
        raise RuntimeError(
            "ElevenLabs API key is invalid (401). Create a new key with Text to Speech permission."
        )
    if response.status_code == 429:
        raise RuntimeError("ElevenLabs quota exceeded. Wait for reset or upgrade plan.")
    if response.status_code >= 400:
        detail = response.text[:300]
        raise RuntimeError(f"ElevenLabs TTS failed ({response.status_code}): {detail}")

    content = response.content
    if not content:
        raise RuntimeError("ElevenLabs returned empty audio.")
    logger.info("ElevenLabs TTS ok voice=%s chars=%s", voice_id, len(text))
    return content
