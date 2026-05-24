import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request

from app.schemas import (
    ComposeFilmRequest,
    ImageResponse,
    SegmentRequest,
    SegmentResponse,
    VideoFromImageRequest,
    VideoGenerateRequest,
    VideoResponse,
    VoiceRequest,
    VoiceResponse,
)
from app.core.config import settings
from app.services.ffmpeg_mux import concat_mp3_files, mux_video_audio
from app.services.image_generation import generate_image_file
from app.services.segmentation import split_story_to_scenes
from app.services.storage import VIDEOS_DIR, new_audio_path, new_image_path, new_video_path
from app.providers.video_model import build_motion_prompt, generate_video_file
from app.services.voice_generation import synthesize_voice_mp3


router = APIRouter(prefix="", tags=["generation"])


@router.post("/segment", response_model=SegmentResponse)
def segment_story(payload: SegmentRequest) -> SegmentResponse:
    try:
        return split_story_to_scenes(payload.text)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/generate_image", response_model=ImageResponse)
async def generate_image(
    request: Request,
    text: str = Query(
        ...,
        min_length=1,
        description="Scene description for the image.",
    ),
    style: str = Query(
        ...,
        min_length=1,
        description="Visual style.",
    ),
    emotion: str = Query(
        ...,
        min_length=1,
        description="Mood / emotion of the scene.",
    ),
) -> ImageResponse:
    try:
        output = new_image_path()
        await generate_image_file(prompt=text, style=style, emotion=emotion, output_path=output)
        base = settings.api_base_url(str(request.base_url))
        image_url = f"{base}/media/images/{output.name}"
        return ImageResponse(image_path=image_url)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Image generation failed: {str(exc)}") from exc


@router.post("/generate_video", response_model=VideoResponse)
async def generate_video(payload: VideoGenerateRequest, request: Request) -> VideoResponse:
    if settings.video_token():
        raise HTTPException(
            status_code=400,
            detail=(
                "Stable Video Diffusion needs a scene image — it cannot animate text alone. "
                "Step 1: POST /generate_image → copy image_path. "
                "Step 2: POST /generate_video_from_images with that image_url."
            ),
        )
    try:
        output = new_video_path()
        base = settings.api_base_url(str(request.base_url))
        scene_line = f"{payload.text}. Mood: {payload.emotion}. Style: {payload.style}."
        source = await generate_video_file(
            output_path=output,
            prompt=scene_line,
            style=payload.style,
            image_urls=None,
            scene_texts=[scene_line],
            seconds_per_scene=payload.seconds_per_scene,
            request_base=base,
        )
        video_url = f"{base}/media/videos/{output.name}"
        return VideoResponse(video_url=video_url, source=source)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Video generation failed: {str(exc)}") from exc


@router.post("/generate_video_from_images", response_model=VideoResponse)
async def generate_video_from_images(
    payload: VideoFromImageRequest, request: Request
) -> VideoResponse:
    try:
        output = new_video_path()
        base = settings.api_base_url(str(request.base_url))
        prompt = build_motion_prompt(
            text=payload.text, style=payload.style, emotion=payload.emotion
        )
        source = await generate_video_file(
            output_path=output,
            prompt=prompt,
            style=payload.style,
            image_urls=[payload.image_url.strip()],
            seconds_per_scene=payload.seconds_per_scene,
            request_base=base,
        )
        if source != "kling" and source not in ("svd", "ai_video") and settings.video_token():
            raise HTTPException(
                status_code=502,
                detail=(
                    f"Expected animated AI video but got fallback '{source}'. "
                    "Check Replicate credits and VIDEO_MODEL in .env. "
                    "Set ALLOW_AI_FALLBACK=false to block static slideshow."
                ),
            )
        return VideoResponse(video_url=f"{base}/media/videos/{output.name}", source=source)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Video from images failed: {str(exc)}") from exc


@router.post("/generate_voice", response_model=VoiceResponse)
async def generate_voice(payload: VoiceRequest, request: Request) -> VoiceResponse:
    try:
        output = new_audio_path()
        await synthesize_voice_mp3(payload.text, payload.voice, output)
        base = settings.api_base_url(str(request.base_url))
        return VoiceResponse(audio_url=f"{base}/media/audio/{output.name}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Voice generation failed: {str(exc)}") from exc


@router.post("/compose_film", response_model=VideoResponse)
async def compose_film(payload: ComposeFilmRequest, request: Request) -> VideoResponse:
    if payload.scene_narrations:
        if len(payload.scene_narrations) != len(payload.image_urls):
            raise HTTPException(
                status_code=400,
                detail="scene_narrations must have the same length as image_urls.",
            )

    has_full = bool(payload.narration_text and payload.narration_text.strip())
    has_scenes = bool(payload.scene_narrations)
    has_voice = has_full or has_scenes

    base = settings.api_base_url(str(request.base_url))
    final_path = new_video_path()

    if not has_voice:
        try:
            source = await generate_video_file(
                output_path=final_path,
                prompt="Composed short film from scenes",
                style="Cinematic",
                image_urls=payload.image_urls,
                seconds_per_scene=payload.seconds_per_scene,
                request_base=base,
            )
            return VideoResponse(video_url=f"{base}/media/videos/{final_path.name}", source=source)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    silent_path = VIDEOS_DIR / f"_silent_{uuid.uuid4().hex}.mp4"
    try:
        source = await generate_video_file(
            output_path=silent_path,
            prompt="Composed short film from scenes",
            style="Cinematic",
            image_urls=payload.image_urls,
            seconds_per_scene=payload.seconds_per_scene,
            request_base=base,
        )

        if payload.scene_narrations:
            part_paths: list[str] = []
            with tempfile.TemporaryDirectory() as tmp:
                for idx, line in enumerate(payload.scene_narrations):
                    part_file = Path(tmp) / f"n{idx}.mp3"
                    await synthesize_voice_mp3(line, payload.voice, part_file)
                    part_paths.append(str(part_file))
                merged_mp3 = new_audio_path()
                concat_mp3_files(part_paths, str(merged_mp3))
                mux_video_audio(str(silent_path), str(merged_mp3), str(final_path))
        else:
            narration_mp3 = new_audio_path()
            await synthesize_voice_mp3(payload.narration_text or "", payload.voice, narration_mp3)
            mux_video_audio(str(silent_path), str(narration_mp3), str(final_path))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Compose film failed: {str(exc)}") from exc
    finally:
        silent_path.unlink(missing_ok=True)

    return VideoResponse(video_url=f"{base}/media/videos/{final_path.name}", source=source)
