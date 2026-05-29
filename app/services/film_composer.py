"""Compose multi-scene films with optional narration (shared by sync + async routes)."""

from __future__ import annotations

import logging
import tempfile
import uuid
from pathlib import Path
from typing import Callable

from fastapi import HTTPException

from app.core.config import settings
from app.firestore_db import create_project
from app.providers.video_model import generate_video_file
from app.schemas import ComposeFilmRequest, ProjectCreate, VideoResponse
from app.services.ffmpeg_mux import concat_mp3_files, mux_video_audio
from app.services.storage import VIDEOS_DIR, new_audio_path, new_video_path
from app.services.voice_generation import ensure_elevenlabs_usable, synthesize_voice_mp3

logger = logging.getLogger("easemovie.film")

ProgressCallback = Callable[[float, str], None]


async def run_compose_film(
    payload: ComposeFilmRequest,
    *,
    base: str,
    on_progress: ProgressCallback | None = None,
) -> VideoResponse:
    if payload.scene_narrations:
        if len(payload.scene_narrations) != len(payload.image_urls):
            raise HTTPException(
                status_code=400,
                detail="scene_narrations must have the same length as image_urls.",
            )

    has_full = bool(payload.narration_text and payload.narration_text.strip())
    has_scenes = bool(payload.scene_narrations)
    has_voice = has_full or has_scenes
    final_path = new_video_path()

    def _project_scenes() -> list[str]:
        if payload.scenes:
            return payload.scenes
        if payload.scene_narrations:
            return payload.scene_narrations
        if payload.narration_text and payload.narration_text.strip():
            return [payload.narration_text.strip()]
        return []

    def _save_project_if_requested(video_name: str) -> None:
        if not payload.save_project:
            return
        if not payload.user_id or not payload.title or not payload.style:
            raise HTTPException(
                status_code=400,
                detail="user_id, title, and style are required to save project metadata.",
            )
        try:
            create_project(
                ProjectCreate(
                    user_id=payload.user_id,
                    title=payload.title,
                    style=payload.style,
                    video_url=f"{base}/media/videos/{video_name}",
                    thumbnail_url=payload.thumbnail_url or "",
                    scenes=_project_scenes(),
                )
            )
        except Exception as exc:
            logger.warning(
                "Video saved but Firestore project save failed (video still returned): %s", exc
            )

    def _progress(value: float, message: str) -> None:
        if on_progress:
            on_progress(value, message)

    _progress(0.05, "Starting film composition")

    use_elevenlabs = False
    if has_voice:
        use_elevenlabs = await ensure_elevenlabs_usable()
        if not use_elevenlabs and (settings.elevenlabs_api_key or "").strip():
            _progress(0.06, "ElevenLabs unavailable — Edge TTS narration")

    if not has_voice:
        _progress(0.15, "Generating animated scenes")
        source = await generate_video_file(
            output_path=final_path,
            prompt="Composed short film from scenes",
            style=payload.style or "Cinematic",
            image_urls=payload.image_urls,
            scene_texts=payload.scene_narrations or payload.scenes,
            scene_emotions=payload.scene_moods,
            seconds_per_scene=payload.seconds_per_scene,
            request_base=base,
        )
        _progress(0.9, "Saving project metadata")
        _save_project_if_requested(final_path.name)
        _progress(1.0, "Completed")
        return VideoResponse(video_url=f"{base}/media/videos/{final_path.name}", source=source)

    silent_path = VIDEOS_DIR / f"_silent_{uuid.uuid4().hex}.mp4"
    narration_choice = None
    story_context = (
        payload.story_context
        or " ".join(payload.scene_narrations or [])
        or (payload.narration_text or "").strip()
    )
    try:
        _progress(0.1, "Generating animated scene clips")
        source = await generate_video_file(
            output_path=silent_path,
            prompt="Composed short film from scenes",
            style=payload.style or "Cinematic",
            image_urls=payload.image_urls,
            scene_texts=payload.scene_narrations or payload.scenes,
            scene_emotions=payload.scene_moods,
            seconds_per_scene=payload.seconds_per_scene,
            request_base=base,
        )

        _progress(0.65, "Synthesizing narration")
        if payload.scene_narrations:
            part_paths: list[str] = []
            total = len(payload.scene_narrations)
            with tempfile.TemporaryDirectory() as tmp:
                for idx, line in enumerate(payload.scene_narrations):
                    part_file = Path(tmp) / f"n{idx}.mp3"
                    scene_mood = None
                    if payload.scene_moods and idx < len(payload.scene_moods):
                        scene_mood = payload.scene_moods[idx]
                    choice = await synthesize_voice_mp3(
                        line,
                        payload.voice,
                        part_file,
                        story_context=story_context,
                        mood_override=scene_mood,
                        use_elevenlabs=use_elevenlabs,
                    )
                    if narration_choice is None:
                        narration_choice = choice
                    part_paths.append(str(part_file))
                    _progress(0.65 + (0.2 * (idx + 1) / total), f"Voice scene {idx + 1}/{total}")
                merged_mp3 = new_audio_path()
                concat_mp3_files(part_paths, str(merged_mp3))
                _progress(0.9, "Mixing audio and video")
                mux_video_audio(str(silent_path), str(merged_mp3), str(final_path))
        else:
            narration_mp3 = new_audio_path()
            narration_choice = await synthesize_voice_mp3(
                payload.narration_text or "",
                payload.voice,
                narration_mp3,
                story_context=story_context,
                use_elevenlabs=use_elevenlabs,
            )
            _progress(0.9, "Mixing audio and video")
            mux_video_audio(str(silent_path), str(narration_mp3), str(final_path))

        _save_project_if_requested(final_path.name)
    finally:
        silent_path.unlink(missing_ok=True)

    _progress(1.0, "Completed")
    return VideoResponse(
        video_url=f"{base}/media/videos/{final_path.name}",
        source=source,
        voice=narration_choice.voice_id if narration_choice else None,
        voice_name=narration_choice.voice_name if narration_choice else None,
        provider=narration_choice.provider if narration_choice else None,
    )
