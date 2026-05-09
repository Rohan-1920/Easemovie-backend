from pathlib import Path

import httpx
from PIL import Image, ImageDraw

from app.core.config import settings


async def generate_image_file(prompt: str, style: str, emotion: str, output_path: Path) -> None:
    if settings.stability_api_key:
        try:
            image_bytes = await _generate_with_stability(prompt, style, emotion)
            output_path.write_bytes(image_bytes)
            return
        except Exception:
            # Stability call fail ho to request fail na ho; local fallback image return karo.
            pass
    _create_fallback_image(output_path, f"{style} | {emotion}\n{prompt[:120]}", 1024, 1024)


async def _generate_with_stability(prompt: str, style: str, emotion: str) -> bytes:
    headers = {
        "Authorization": f"Bearer {settings.stability_api_key}",
        "Accept": "image/*",
    }
    final_prompt = f"{prompt}. Mood: {emotion}. Style: {style}."
    # Stability endpoint multipart/form-data expect karta hai.
    files = {
        "prompt": (None, final_prompt),
        "output_format": (None, "png"),
        "style_preset": (None, _map_style(style)),
    }

    timeout = httpx.Timeout(connect=20.0, read=120.0, write=20.0, pool=20.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(settings.stability_base_url, headers=headers, files=files)
    if response.status_code != 200:
        raise RuntimeError(f"Stability AI error: {response.status_code} {response.text[:300]}")
    return response.content


def _create_fallback_image(output_path: Path, text: str, width: int, height: int) -> None:
    image = Image.new("RGB", (width, height), (24, 28, 34))
    draw = ImageDraw.Draw(image)
    draw.rectangle([(40, 40), (width - 40, height - 40)], outline=(90, 170, 255), width=3)
    draw.multiline_text((70, 90), text, fill=(235, 235, 235), spacing=10)
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
