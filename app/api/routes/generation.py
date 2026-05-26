import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request, Response

from app.schemas import (
    ComposeFilmRequest,
    ImageResponse,
    JobStatusResponse,
    SegmentRequest,
    SegmentResponse,
    VideoFromImageRequest,
    VideoGenerateRequest,
    VideoResponse,
    VoiceRequest,
    VoiceResponse,
)
from app.core.config import settings
from app.services.image_generation import generate_image_file
from app.services.segmentation import split_story_to_scenes
from app.services.storage import new_image_path
from app.services.film_composer import run_compose_film
from app.services.video_pipeline import run_video_from_image
from app.services.generation_jobs import (
    create_job,
    get_job,
    job_to_dict,
    run_in_background,
    update_job_progress,
)
from app.services.voice_generation import synthesize_voice_mp3
from app.services.storage import new_audio_path


router = APIRouter(prefix="", tags=["generation"])


def _use_async(async_mode: bool | None) -> bool:
    if async_mode is None:
        return settings.generation_async_default
    return async_mode


def _schedule(coro, *, job_id: str) -> None:
    asyncio.create_task(run_in_background(coro, job_id=job_id))


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
        base = settings.api_base_url(str(request.base_url))
        return ImageResponse(image_path=f"{base}/media/images/{output.name}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Image generation failed: {str(exc)}") from exc


@router.post("/generate_video", response_model=VideoResponse)
async def generate_video(payload: VideoGenerateRequest, request: Request) -> VideoResponse:
    if settings.video_token():
        raise HTTPException(
            status_code=400,
            detail=(
                "Stable Video Diffusion needs a scene image — use POST /generate_video_from_images "
                "or POST /compose_film for multi-scene films."
            ),
        )
    try:
        from app.providers.video_model import generate_video_file
        from app.services.storage import new_video_path

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
        return VideoResponse(video_url=f"{base}/media/videos/{output.name}", source=source)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Video generation failed: {str(exc)}") from exc


@router.post("/generate_video_from_images", response_model=VideoResponse)
async def generate_video_from_images(
    payload: VideoFromImageRequest,
    request: Request,
    response: Response,
    async_mode: bool | None = Query(
        default=None,
        description="true = return job_id immediately (recommended on Render). false = wait for video.",
    ),
) -> VideoResponse:
    base = settings.api_base_url(str(request.base_url))

    async def _work() -> VideoResponse:
        result = await run_video_from_image(payload, base=base)
        if result.source not in ("kling", "svd", "svd_multi", "ai_video", "ai_video_multi") and settings.video_token():
            raise HTTPException(
                status_code=502,
                detail=(
                    f"Expected animated AI video but got fallback '{result.source}'. "
                    "Check Replicate credits and VIDEO_MODEL in .env."
                ),
            )
        return result

    if _use_async(async_mode):
        job = create_job("video_from_images")
        _schedule(_work(), job_id=job.id)
        response.status_code = 202
        return VideoResponse(source="job", job_id=job.id)

    try:
        return await _work()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Video from images failed: {str(exc)}") from exc


@router.post("/generate_voice", response_model=VoiceResponse)
async def generate_voice(payload: VoiceRequest, request: Request) -> VoiceResponse:
    try:
        output = new_audio_path()
        choice = await synthesize_voice_mp3(
            payload.text,
            payload.voice,
            output,
            story_context=payload.story_context,
        )
        base = settings.api_base_url(str(request.base_url))
        return VoiceResponse(
            audio_url=f"{base}/media/audio/{output.name}",
            voice=choice.voice_id,
            voice_name=choice.voice_name,
            mood=choice.mood,
            story_genre=choice.story_genre,
            provider=choice.provider,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Voice generation failed: {str(exc)}") from exc


@router.post("/compose_film", response_model=VideoResponse)
async def compose_film(
    payload: ComposeFilmRequest,
    request: Request,
    response: Response,
    async_mode: bool | None = Query(
        default=None,
        description="true = return job_id immediately (recommended). false = wait for full film.",
    ),
) -> VideoResponse:
    base = settings.api_base_url(str(request.base_url))

    if _use_async(async_mode):
        job = create_job("compose_film")

        async def _work_with_job() -> VideoResponse:
            return await run_compose_film(
                payload,
                base=base,
                on_progress=lambda v, m: update_job_progress(job.id, v, m),
            )

        _schedule(_work_with_job(), job_id=job.id)
        response.status_code = 202
        return VideoResponse(source="job", job_id=job.id)

    try:
        return await run_compose_film(payload, base=base)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Compose film failed: {str(exc)}") from exc


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_generation_job(job_id: str) -> JobStatusResponse:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    data = job_to_dict(job)
    return JobStatusResponse(**data)
