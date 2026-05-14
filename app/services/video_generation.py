import io
from urllib.parse import urlparse

import httpx
import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw

from app.services.image_generation import pil_image_to_rgb_opaque
from app.services.storage import MEDIA_ROOT


def _load_rgb_image(url: str, client: httpx.Client) -> Image.Image:
    stripped = url.strip()
    parsed = urlparse(stripped)
    if parsed.scheme in ("http", "https") and parsed.hostname in (
        "127.0.0.1",
        "localhost",
        "0.0.0.0",
    ):
        path_part = parsed.path or ""
        media_prefix = "/media/"
        if path_part.startswith(media_prefix):
            rel = path_part[len(media_prefix) :].lstrip("/").replace("\\", "/")
            local = (MEDIA_ROOT / rel).resolve()
            root = MEDIA_ROOT.resolve()
            try:
                local.relative_to(root)
            except ValueError as exc:
                raise ValueError("Invalid media URL path.") from exc
            if local.is_file():
                with Image.open(local) as opened:
                    return pil_image_to_rgb_opaque(opened)

    response = client.get(stripped)
    response.raise_for_status()
    if len(response.content) > 15 * 1024 * 1024:
        raise ValueError(f"Image too large from URL: {stripped[:80]}")
    with Image.open(io.BytesIO(response.content)) as opened:
        return pil_image_to_rgb_opaque(opened)


def generate_video_from_image_urls(
    image_urls: list[str],
    output_path: str,
    *,
    seconds_per_image: float = 3.0,
    width: int = 1280,
    height: int = 720,
    target_fps: int = 24,
) -> None:
    """Build an MP4 slideshow from scene image URLs (decoded visuals per scene)."""
    if seconds_per_image <= 0:
        seconds_per_image = 3.0
    frames: list[np.ndarray] = []
    repeat = max(1, int(seconds_per_image * target_fps))

    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        for url in image_urls:
            img = _load_rgb_image(url, client)
            img = _resize_cover(img, width, height)
            arr = np.array(img)
            for _ in range(repeat):
                frames.append(arr)

    with imageio.get_writer(output_path, fps=target_fps, codec="libx264", quality=8) as writer:
        for frame in frames:
            writer.append_data(frame)


def _resize_cover(img: Image.Image, w: int, h: int) -> Image.Image:
    iw, ih = img.size
    scale = max(w / iw, h / ih)
    nw, nh = int(iw * scale), int(ih * scale)
    img = img.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - w) // 2
    top = (nh - h) // 2
    return img.crop((left, top, left + w, top + h))


def generate_video_from_scenes(scenes: list[str], style: str, output_path: str) -> None:
    frames: list[np.ndarray] = []
    for scene in scenes:
        img = _scene_text_image(scene=scene, style=style, width=1280, height=720)
        frames.append(np.array(img))

    with imageio.get_writer(output_path, fps=1, codec="libx264", quality=7) as writer:
        for frame in frames:
            writer.append_data(frame)


def _scene_text_image(scene: str, style: str, width: int, height: int) -> Image.Image:
    image = Image.new("RGB", (width, height), (15, 20, 28))
    draw = ImageDraw.Draw(image)
    draw.rectangle([(30, 30), (width - 30, height - 30)], outline=(0, 191, 165), width=4)
    draw.text((70, 90), f"Style: {style}", fill=(173, 255, 233))
    wrapped = _wrap_text(scene, max_chars=70)
    draw.multiline_text((70, 170), wrapped, fill=(245, 245, 245), spacing=10)
    return image


def _wrap_text(text: str, max_chars: int = 60) -> str:
    words = text.split()
    if not words:
        return ""
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        if len(current) + 1 + len(word) <= max_chars:
            current += f" {word}"
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return "\n".join(lines)
