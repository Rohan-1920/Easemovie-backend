"""Image generation — black-forest-labs/flux-dev on Replicate."""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageDraw

from app.core.config import settings
from app.providers import replicate_api

logger = logging.getLogger("easemovie.image")


async def generate_image_file(prompt: str, style: str, emotion: str, output_path: Path) -> None:
    token = settings.image_token()
    model = (settings.image_model or "black-forest-labs/flux-dev").strip()

    if not token:
        if settings.allow_ai_fallback:
            logger.warning("No image API token — using fallback image.")
            _create_fallback_image(output_path, f"{style} | {emotion}\n{prompt[:120]}", 1024, 1024)
            return
        raise RuntimeError(
            "IMAGE_REPLICATE_API_TOKEN is not set. Add it to .env (see .env.example)."
        )

    final_prompt = f"{prompt}. Mood: {emotion}. Style: {style}."
    try:
        prediction = await replicate_api.run_model_prediction(
            model,
            {
                "prompt": final_prompt,
                "aspect_ratio": settings.flux_aspect_ratio,
                "output_format": settings.flux_output_format,
                "output_quality": 90,
                "num_inference_steps": settings.flux_num_inference_steps,
                "guidance": settings.flux_guidance,
                "num_outputs": 1,
            },
            api_token=token,
        )
        url = replicate_api.extract_output_url(prediction.get("output"))
        output_path.write_bytes(await replicate_api.download_url(url))
        logger.info("FLUX image saved: %s", output_path.name)
    except Exception as exc:
        if settings.allow_ai_fallback:
            logger.warning("FLUX failed (%s) — fallback image.", exc)
            _create_fallback_image(output_path, f"{style} | {emotion}\n{prompt[:120]}", 1024, 1024)
            return
        raise RuntimeError(f"FLUX image generation failed: {exc}") from exc


def _create_fallback_image(output_path: Path, text: str, width: int, height: int) -> None:
    image = Image.new("RGB", (width, height), (24, 28, 34))
    draw = ImageDraw.Draw(image)
    draw.rectangle([(40, 40), (width - 40, height - 40)], outline=(90, 170, 255), width=3)
    draw.multiline_text((70, 90), text, fill=(235, 235, 235), spacing=10)
    image.save(output_path, format="PNG")
