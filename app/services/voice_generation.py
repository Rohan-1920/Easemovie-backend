from __future__ import annotations

from pathlib import Path

import edge_tts


async def synthesize_voice_mp3(text: str, voice: str, output_path: Path) -> None:
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("Voice text cannot be empty.")
    communicate = edge_tts.Communicate(cleaned, voice)
    await communicate.save(str(output_path))
