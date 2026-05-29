"""Video generation — Replicate image-to-video (sunfjun SVD budget / optional Kling)."""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
import uuid
from pathlib import Path

from app.core.config import settings
from app.core.media_urls import is_local_host, local_media_path_from_url, to_public_media_url
from app.providers import replicate_api
from app.services.ffmpeg_mux import concat_video_files
from app.services.storage import VIDEOS_DIR
from app.services.video_slideshow import generate_slideshow_from_image_urls

logger = logging.getLogger("easemovie.video")


def is_ai_video_configured() -> bool:
    return bool(settings.video_token() and (settings.video_model or "").strip())


def build_motion_prompt(*, text: str, style: str, emotion: str) -> str:
    """Motion + scene prompt sent to the video model (Kling uses this for animation)."""
    return (
        f"{text.strip()}. "
        f"Style: {style.strip()}. Mood: {emotion.strip()}. "
        "Cinematic animated motion, characters and environment moving naturally, "
        "smooth camera movement, high quality animation."
    )


def video_source_label(model_slug: str, *, multi_scene: bool = False) -> str:
    slug = (model_slug or "").lower()
    if "kling" in slug:
        return "kling"
    if "stable-video" in slug or "svd" in slug:
        return "svd_multi" if multi_scene else "svd"
    return "ai_video_multi" if multi_scene else "ai_video"


def _build_model_input(model_slug: str, *, motion_prompt: str, input_image_url: str) -> dict:
    slug = (model_slug or "").lower()
    if "kling" in slug:
        duration = settings.kling_duration
        if duration not in (5, 10):
            duration = 5
        payload: dict = {
            "prompt": motion_prompt,
            "start_image": input_image_url,
            "duration": duration,
            "aspect_ratio": settings.kling_aspect_ratio,
        }
        negative = (settings.kling_negative_prompt or "").strip()
        if negative:
            payload["negative_prompt"] = negative
        return payload

    return {
        "input_image": input_image_url,
        "video_length": settings.svd_video_length,
        "sizing_strategy": "maintain_aspect_ratio",
        "frames_per_second": settings.svd_frames_per_second,
        "motion_bucket_id": settings.svd_motion_bucket_id,
        "cond_aug": settings.svd_cond_aug,
        "decoding_t": settings.svd_decoding_t,
    }


async def resolve_input_image_for_video(
    image_url: str, api_token: str, request_base: str = ""
) -> str:
    """Upload local scene PNG to Replicate when needed (LAN URLs are not reachable by Replicate)."""
    public_url = to_public_media_url(image_url, request_base)
    local_path = local_media_path_from_url(image_url) or local_media_path_from_url(public_url)

    if local_path and local_path.is_file():
        logger.info("Uploading scene image to Replicate: %s", local_path.name)
        return await replicate_api.upload_local_file(local_path, api_token)

    from urllib.parse import urlparse

    parsed = urlparse(public_url or image_url)
    if public_url and parsed.hostname and not is_local_host(parsed.hostname):
        return public_url

    raise RuntimeError(
        "Could not resolve scene image. Use image_path from POST /generate_image "
        "(file must exist under media/images/)."
    )


def _scene_motion_text(
    index: int,
    *,
    scene_texts: list[str] | None,
    fallback_prompt: str,
) -> str:
    if scene_texts and index < len(scene_texts):
        line = (scene_texts[index] or "").strip()
        if line:
            return line
    cleaned = (fallback_prompt or "").strip()
    if cleaned and cleaned.lower() != "composed short film from scenes":
        return cleaned
    return f"Cinematic story scene {index + 1} with natural motion and depth"


def _scene_emotion(index: int, scene_emotions: list[str] | None) -> str:
    if scene_emotions and index < len(scene_emotions):
        mood = (scene_emotions[index] or "").strip()
        if mood:
            return mood
    return "neutral"


async def generate_video_file(
    *,
    output_path: Path,
    prompt: str,
    style: str,
    image_urls: list[str] | None = None,
    scene_texts: list[str] | None = None,
    scene_emotions: list[str] | None = None,
    seconds_per_scene: float = 3.0,
    request_base: str = "",
) -> str:
    """Returns source label: kling | svd | svd_multi | ai_video | slideshow_*."""
    token = settings.video_token()
    model = (settings.video_model or "sunfjun/stable-video-diffusion").strip()
    urls = [u.strip() for u in (image_urls or []) if u and u.strip()]

    if settings.compose_fast_video and urls:
        await asyncio.to_thread(
            generate_slideshow_from_image_urls,
            urls,
            str(output_path),
            seconds_per_image=seconds_per_scene,
        )
        logger.info("Fast compose slideshow: %s scenes", len(urls))
        return "slideshow_fast"

    if token and len(urls) > 1:
        try:
            source = await _generate_multi_scene_ai_video(
                api_token=token,
                model_slug=model,
                output_path=output_path,
                image_urls=urls,
                style=style,
                fallback_prompt=prompt,
                scene_texts=scene_texts,
                scene_emotions=scene_emotions,
                request_base=request_base,
            )
            logger.info("Multi-scene AI video saved (%s): %s", source, output_path.name)
            return source
        except Exception as exc:
            if not settings.allow_ai_fallback:
                raise RuntimeError(f"Multi-scene AI video failed ({model}): {exc}") from exc
            logger.warning("Multi-scene AI video failed (%s) — slideshow fallback.", exc)

    if token and len(urls) == 1:
        text = _scene_motion_text(0, scene_texts=scene_texts, fallback_prompt=prompt)
        emotion = _scene_emotion(0, scene_emotions)
        motion_prompt = build_motion_prompt(text=text, style=style, emotion=emotion)
        input_image = await resolve_input_image_for_video(urls[0], token, request_base=request_base)
        try:
            await _generate_ai_video(
                api_token=token,
                model_slug=model,
                output_path=output_path,
                motion_prompt=motion_prompt,
                input_image_url=input_image,
            )
            source = video_source_label(model)
            logger.info("AI video saved (%s): %s", source, output_path.name)
            return source
        except Exception as exc:
            if not settings.allow_ai_fallback:
                raise RuntimeError(f"AI video generation failed ({model}): {exc}") from exc
            logger.warning("AI video failed (%s) — slideshow fallback.", exc)

    if urls:
        generate_slideshow_from_image_urls(
            urls,
            str(output_path),
            seconds_per_image=seconds_per_scene,
        )
        return "slideshow_images"

    if scene_texts:
        from app.services.video_slideshow import generate_slideshow_from_scene_text

        generate_slideshow_from_scene_text(scene_texts, style, str(output_path))
        return "slideshow_text"

    if not token:
        raise RuntimeError(
            "VIDEO_REPLICATE_API_TOKEN is not set and no image_urls were provided for slideshow."
        )
    raise RuntimeError("Video generation failed: provide image_url from /generate_image first.")


async def _generate_multi_scene_ai_video(
    *,
    api_token: str,
    model_slug: str,
    output_path: Path,
    image_urls: list[str],
    style: str,
    fallback_prompt: str,
    scene_texts: list[str] | None,
    scene_emotions: list[str] | None,
    request_base: str,
) -> str:
    clip_paths: list[str] = []
    tmp_dir = VIDEOS_DIR / f"_clips_{uuid.uuid4().hex}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    try:
        async def _render_scene(index: int, image_url: str) -> str:
            text = _scene_motion_text(index, scene_texts=scene_texts, fallback_prompt=fallback_prompt)
            emotion = _scene_emotion(index, scene_emotions)
            motion_prompt = build_motion_prompt(text=text, style=style, emotion=emotion)
            input_image = await resolve_input_image_for_video(
                image_url, api_token, request_base=request_base
            )
            clip_path = tmp_dir / f"scene_{index + 1}.mp4"
            logger.info("SVD scene %s/%s: %s", index + 1, len(image_urls), image_url[:80])
            await _generate_ai_video(
                api_token=api_token,
                model_slug=model_slug,
                output_path=clip_path,
                motion_prompt=motion_prompt,
                input_image_url=input_image,
            )
            return str(clip_path)

        if settings.svd_parallel_scenes and len(image_urls) > 1:
            clip_paths = list(
                await asyncio.gather(
                    *[_render_scene(i, url) for i, url in enumerate(image_urls)]
                )
            )
        else:
            for index, image_url in enumerate(image_urls):
                clip_paths.append(await _render_scene(index, image_url))

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False, dir=VIDEOS_DIR) as merged:
            merged_path = merged.name
        try:
            concat_video_files(clip_paths, merged_path)
            output_path.write_bytes(Path(merged_path).read_bytes())
        finally:
            Path(merged_path).unlink(missing_ok=True)
    finally:
        for clip in clip_paths:
            Path(clip).unlink(missing_ok=True)
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)

    return video_source_label(model_slug, multi_scene=True)


async def _generate_ai_video(
    *,
    api_token: str,
    model_slug: str,
    output_path: Path,
    motion_prompt: str,
    input_image_url: str,
) -> None:
    input_data = _build_model_input(
        model_slug,
        motion_prompt=motion_prompt,
        input_image_url=input_image_url,
    )
    prediction = await replicate_api.run_model_prediction(
        model_slug,
        input_data,
        api_token=api_token,
    )
    url = replicate_api.extract_output_url(prediction.get("output"))
    output_path.write_bytes(await replicate_api.download_url(url))
