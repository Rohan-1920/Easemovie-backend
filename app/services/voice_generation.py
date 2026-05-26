from __future__ import annotations

from pathlib import Path

import edge_tts

from app.core.config import settings
from app.providers.elevenlabs_api import synthesize_speech_mp3
from app.services.story_analysis import VoiceChoice, pick_voice_for_text


def elevenlabs_configured() -> bool:
    return bool((settings.elevenlabs_api_key or "").strip())


async def synthesize_voice_mp3(
    text: str,
    voice: str,
    output_path: Path,
    *,
    story_context: str | None = None,
    mood_override: str | None = None,
) -> VoiceChoice:
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("Voice text cannot be empty.")

    choice = pick_voice_for_text(
        cleaned,
        voice=voice,
        story_context=story_context,
        use_elevenlabs=elevenlabs_configured(),
        mood_override=mood_override,
    )

    if choice.provider == "elevenlabs":
        audio = await synthesize_speech_mp3(cleaned, choice.voice_id)
        output_path.write_bytes(audio)
        return choice

    communicate = edge_tts.Communicate(cleaned, choice.voice_id)
    await communicate.save(str(output_path))
    return choice
