import logging
from pathlib import Path

import httpx
from PIL import Image, ImageDraw

from app.core.config import settings

logger = logging.getLogger(__name__)


async def generate_image_file(prompt: str, style: str, emotion: str, output_path: Path) -> None:
    if settings.stability_api_key:
        try:
            image_bytes = await _generate_with_stability(prompt, style, emotion)
            output_path.write_bytes(image_bytes)
            return
        except Exception as e:
            # Log the error for debugging
            logger.error(f"Stability AI image generation failed: {str(e)}", exc_info=True)
    _create_fallback_image(output_path, f"{style} | {emotion}\n{prompt[:120]}", 1024, 1024)


async def _generate_with_stability(prompt: str, style: str, emotion: str) -> bytes:
    if not settings.stability_api_key:
        raise ValueError("Stability API key is not configured")
    
    headers = {
        "Authorization": f"Bearer {settings.stability_api_key}",
        "Accept": "image/*",
    }
    final_prompt = f"{prompt}. Mood: {emotion}. Style: {style}."
    
    # Use JSON payload for v2beta API
    payload = {
        "prompt": final_prompt,
        "output_format": "png",
        "style_preset": _map_style(style),
    }
    
    timeout = httpx.Timeout(connect=20.0, read=120.0, write=20.0, pool=20.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.post(
                settings.stability_base_url,
                headers=headers,
                json=payload,  # Use JSON instead of multipart files
            )
        except httpx.TimeoutException as e:
            logger.error(f"Stability API timeout: {str(e)}")
            raise RuntimeError(f"Stability API timeout: {str(e)}")
        except Exception as e:
            logger.error(f"Stability API connection error: {str(e)}")
            raise RuntimeError(f"Stability API connection error: {str(e)}")
    
    if response.status_code != 200:
        error_msg = f"Stability AI error: {response.status_code}"
        try:
            error_detail = response.text[:500]
            logger.error(f"{error_msg} - {error_detail}")
        except:
            pass
        raise RuntimeError(error_msg)
    
    return response.content


def _create_fallback_image(output_path: Path, text: str, width: int, height: int) -> None:
    image = Image.new("RGB", (width, height), (240, 245, 250))  # Light blue background instead of black
    draw = ImageDraw.Draw(image)
    draw.rectangle([(40, 40), (width - 40, height - 40)], outline=(50, 120, 200), width=3)
    draw.multiline_text((70, 90), text, fill=(30, 40, 80), spacing=10)
    image.save(output_path, format="PNG")


def _map_style(style_name: str) -> str:
    style = style_name.lower()
    if "anime" in style:
        return "anime"
    if "real" in style or "cinematic" in style:
        return "cinematic"
    if "3d" in style:
        return "3d-model"
    return "digital-art"
