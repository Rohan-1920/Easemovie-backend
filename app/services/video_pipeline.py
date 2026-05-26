"""Single-scene and multi-scene video generation helpers."""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

from app.providers.video_model import build_motion_prompt, generate_video_file
from app.schemas import VideoFromImageRequest, VideoResponse
from app.services.storage import new_video_path


async def run_video_from_image(
    payload: VideoFromImageRequest,
    *,
    base: str,
) -> VideoResponse:
    output = new_video_path()
    image_urls = [u.strip() for u in payload.image_urls if u and u.strip()]
    if not image_urls and payload.image_url:
        image_urls = [payload.image_url.strip()]
    if not image_urls:
        raise HTTPException(status_code=400, detail="image_url or image_urls is required.")

    prompt = build_motion_prompt(text=payload.text, style=payload.style, emotion=payload.emotion)
    source = await generate_video_file(
        output_path=output,
        prompt=prompt,
        style=payload.style,
        image_urls=image_urls,
        scene_texts=payload.scene_texts or [payload.text],
        scene_emotions=payload.scene_emotions or [payload.emotion],
        seconds_per_scene=payload.seconds_per_scene,
        request_base=base,
    )
    return VideoResponse(video_url=f"{base}/media/videos/{output.name}", source=source)
