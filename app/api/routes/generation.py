import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request

from app.schemas import (
    ComposeFilmRequest,
    ImageResponse,
    SegmentRequest,
    SegmentResponse,
    VideoFromImagesRequest,
    VideoRequest,
    VideoResponse,
    VoiceRequest,
    VoiceResponse,
)
from app.services.ffmpeg_mux import concat_mp3_files, mux_video_audio
from app.services.image_generation import generate_image_file
from app.services.segmentation import split_story_to_scenes
from app.services.storage import VIDEOS_DIR, new_audio_path, new_image_path, new_video_path
from app.services.video_generation import (
    generate_video_from_image_urls,
    generate_video_from_scenes,
)
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
    text: str = Query(..., min_length=1),
    style: str = Query(..., min_length=1),
    emotion: str = Query(..., min_length=1),
) -> ImageResponse:
    try:
        output = new_image_path()
        await generate_image_file(prompt=text, style=style, emotion=emotion, output_path=output)
        image_url = str(request.base_url).rstrip("/") + f"/media/images/{output.name}"
        return ImageResponse(image_path=image_url)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Image generation failed: {str(exc)}") from exc


@router.post("/generate_video", response_model=VideoResponse)
def generate_video(payload: VideoRequest, request: Request) -> VideoResponse:
    if not payload.scenes:
        raise HTTPException(status_code=400, detail="At least one scene is required.")
    try:
        output = new_video_path()
        generate_video_from_scenes(scenes=payload.scenes, style=payload.style, output_path=str(output))
        video_url = str(request.base_url).rstrip("/") + f"/media/videos/{output.name}"
        return VideoResponse(video_url=video_url)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Video generation failed: {str(exc)}") from exc


@router.post("/generate_video_from_images", response_model=VideoResponse)
def generate_video_from_images(payload: VideoFromImagesRequest, request: Request) -> VideoResponse:
    try:
        output = new_video_path()
        generate_video_from_image_urls(
            payload.image_urls,
            str(output),
            seconds_per_image=payload.seconds_per_scene,
        )
        base = str(request.base_url).rstrip("/")
        return VideoResponse(video_url=f"{base}/media/videos/{output.name}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Video from images failed: {str(exc)}") from exc


@router.post("/generate_voice", response_model=VoiceResponse)
async def generate_voice(payload: VoiceRequest, request: Request) -> VoiceResponse:
    try:
        output = new_audio_path()
        await synthesize_voice_mp3(payload.text, payload.voice, output)
        base = str(request.base_url).rstrip("/")
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

    base = str(request.base_url).rstrip("/")
    final_path = new_video_path()

    if not has_voice:
        try:
            generate_video_from_image_urls(
                payload.image_urls,
                str(final_path),
                seconds_per_image=payload.seconds_per_scene,
            )
            return VideoResponse(video_url=f"{base}/media/videos/{final_path.name}")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    silent_path = VIDEOS_DIR / f"_silent_{uuid.uuid4().hex}.mp4"
    try:
        generate_video_from_image_urls(
            payload.image_urls,
            str(silent_path),
            seconds_per_image=payload.seconds_per_scene,
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

    return VideoResponse(video_url=f"{base}/media/videos/{final_path.name}")
