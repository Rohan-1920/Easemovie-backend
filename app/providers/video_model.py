"""Video generation — Replicate image-to-video (sunfjun SVD budget / optional Kling)."""

from __future__ import annotations

import logging
from pathlib import Path

from app.core.config import settings
from app.core.media_urls import is_local_host, local_media_path_from_url, to_public_media_url
from app.providers import replicate_api
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


def video_source_label(model_slug: str) -> str:
    slug = (model_slug or "").lower()
    if "kling" in slug:
        return "kling"
    if "stable-video" in slug or "svd" in slug:
        return "svd"
    return "ai_video"


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


async def generate_video_file(
    *,
    output_path: Path,
    prompt: str,
    style: str,
    image_urls: list[str] | None = None,
    scene_texts: list[str] | None = None,
    seconds_per_scene: float = 3.0,
    request_base: str = "",
) -> str:
    """Returns source label: kling | svd | ai_video | slideshow_images | slideshow_text."""
    token = settings.video_token()
    model = (settings.video_model or "sunfjun/stable-video-diffusion").strip()

    if token and image_urls:
        input_image = await resolve_input_image_for_video(
            image_urls[0], token, request_base=request_base
        )
        try:
            await _generate_ai_video(
                api_token=token,
                model_slug=model,
                output_path=output_path,
                motion_prompt=prompt,
                input_image_url=input_image,
            )
            source = video_source_label(model)
            logger.info("AI video saved (%s): %s", source, output_path.name)
            return source
        except Exception as exc:
            if not settings.allow_ai_fallback:
                raise RuntimeError(
                    f"AI video generation failed ({model}): {exc}"
                ) from exc
            logger.warning("AI video failed (%s) — slideshow fallback.", exc)

    if image_urls:
        generate_slideshow_from_image_urls(
            image_urls,
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
