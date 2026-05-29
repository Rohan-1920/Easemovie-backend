from __future__ import annotations

import logging
from pathlib import Path

import edge_tts

from app.core.config import settings
from app.core.startup_checks import is_valid_elevenlabs_key
from app.providers.elevenlabs_api import synthesize_speech_mp3, verify_api_key
from app.services.story_analysis import VoiceChoice, pick_voice_for_text

logger = logging.getLogger("easemovie.voice")

# Set once per process when /v1/user rejects the key — avoids retrying ElevenLabs every scene.
_elevenlabs_rejected: bool = False


def elevenlabs_configured() -> bool:
    key = (settings.elevenlabs_api_key or "").strip()
    if not key or not is_valid_elevenlabs_key(key):
        return False
    return not _elevenlabs_rejected


async def ensure_elevenlabs_usable() -> bool:
    """Verify key with ElevenLabs before long video jobs (fail fast)."""
    global _elevenlabs_rejected
    if not (settings.elevenlabs_api_key or "").strip():
        return False
    if _elevenlabs_rejected:
        return False
    if not is_valid_elevenlabs_key(settings.elevenlabs_api_key):
        logger.warning("ELEVENLABS_API_KEY looks like a placeholder — using Edge TTS.")
        _elevenlabs_rejected = True
        return False
    ok, err = await verify_api_key()
    if not ok:
        logger.warning("%s — using Edge TTS for narration.", err)
        _elevenlabs_rejected = True
        return False
    return True


async def synthesize_voice_mp3(
    text: str,
    voice: str,
    output_path: Path,
    *,
    story_context: str | None = None,
    mood_override: str | None = None,
    use_elevenlabs: bool | None = None,
) -> VoiceChoice:
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("Voice text cannot be empty.")

    if use_elevenlabs is None:
        use_elevenlabs = elevenlabs_configured()

    choice = pick_voice_for_text(
        cleaned,
        voice=voice,
        story_context=story_context,
        use_elevenlabs=use_elevenlabs,
        mood_override=mood_override,
    )

    if choice.provider == "elevenlabs":
        try:
            audio = await synthesize_speech_mp3(cleaned, choice.voice_id)
            output_path.write_bytes(audio)
            return choice
        except RuntimeError as exc:
            global _elevenlabs_rejected
            msg = str(exc).lower()
            if "invalid" in msg or "401" in msg or "quota" in msg or "not set" in msg:
                logger.warning("ElevenLabs failed (%s) — falling back to Edge TTS.", exc)
                _elevenlabs_rejected = True
                edge_choice = pick_voice_for_text(
                    cleaned,
                    voice=voice,
                    story_context=story_context,
                    use_elevenlabs=False,
                    mood_override=mood_override,
                )
                communicate = edge_tts.Communicate(cleaned, edge_choice.voice_id)
                await communicate.save(str(output_path))
                return edge_choice
            raise

    communicate = edge_tts.Communicate(cleaned, choice.voice_id)
    await communicate.save(str(output_path))
    return choice
