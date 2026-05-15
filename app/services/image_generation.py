import asyncio
import io
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from PIL import Image, ImageDraw

from app.core.config import settings

logger = logging.getLogger(__name__)

GenerateFn = Callable[[str, str, str], Awaitable[bytes]]


def pil_image_to_rgb_opaque(img: Image.Image) -> Image.Image:
    """Composite transparency onto white so RGB conversion never yields black voids."""
    if img.mode == "RGBA":
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        return background
    if img.mode == "LA":
        rgba = img.convert("RGBA")
        return pil_image_to_rgb_opaque(rgba)
    if img.mode == "P":
        if "transparency" in img.info:
            return pil_image_to_rgb_opaque(img.convert("RGBA"))
        return img.convert("RGB")
    return img.convert("RGB")


def _normalize_png_bytes(raw: bytes) -> bytes:
    """Decode API PNG/JPEG, flatten alpha, re-encode as PNG for storage and video pipeline."""
    with Image.open(io.BytesIO(raw)) as decoded:
        rgb = pil_image_to_rgb_opaque(decoded)
        out = io.BytesIO()
        rgb.save(out, format="PNG")
        return out.getvalue()


def _build_final_prompt(prompt: str, style: str, emotion: str) -> str:
    cleaned = prompt.strip().lstrip(".").strip()
    return f"{cleaned}. Mood: {emotion}. Style: {style}."


async def generate_image_file(prompt: str, style: str, emotion: str, output_path: Path) -> None:
    chain = _provider_chain()
    if not chain:
        msg = (
            "No image provider configured. Set FAL_API_KEY in .env (quotes required: "
            'FAL_API_KEY="id:secret") or enable POLLINATIONS_FALLBACK_ENABLED=true. '
            "Get a fal key at https://fal.ai/dashboard/keys"
        )
        logger.error(msg)
        if settings.image_allow_placeholder_fallback:
            _create_fallback_image(output_path, f"{style} | {emotion}\n{prompt[:120]}", 1024, 1024)
            return
        raise RuntimeError(msg)

    errors: list[str] = []
    for name, generate in chain:
        try:
            image_bytes = await generate(prompt, style, emotion)
            output_path.write_bytes(image_bytes)
            logger.info("Image generated via %s (%s bytes)", name, len(image_bytes))
            return
        except Exception as e:
            errors.append(f"{name}: {e}")
            logger.error("%s image generation failed: %s", name, e, exc_info=True)

    detail = "; ".join(errors) if errors else "unknown error"
    logger.error("All image providers failed: %s", detail)
    if settings.image_allow_placeholder_fallback:
        logger.warning("IMAGE_ALLOW_PLACEHOLDER_FALLBACK=true — serving placeholder PNG")
        _create_fallback_image(output_path, f"{style} | {emotion}\n{prompt[:120]}", 1024, 1024)
        return
    raise RuntimeError(f"Image generation failed ({detail})")


def _provider_chain() -> list[tuple[str, GenerateFn]]:
    mode = (settings.image_provider or "auto").lower()
    fal_key = (settings.fal_api_key or "").strip()
    stability_key = (settings.stability_api_key or "").strip()
    poll_fn: tuple[str, GenerateFn] | None = (
        ("pollinations", _generate_with_pollinations)
        if settings.pollinations_fallback_enabled
        else None
    )

    fal_fn: tuple[str, GenerateFn] | None = ("fal", _generate_with_fal) if fal_key else None
    stability_fn: tuple[str, GenerateFn] | None = (
        ("stability", _generate_with_stability) if stability_key else None
    )

    if mode == "fal":
        if not fal_fn:
            logger.warning("IMAGE_PROVIDER=fal but FAL_API_KEY is missing or not loaded from .env")
        chain = [fal_fn] if fal_fn else []
        if poll_fn and not chain:
            chain.append(poll_fn)
        return chain
    if mode == "stability":
        return [stability_fn] if stability_fn else []
    if mode == "pollinations":
        return [poll_fn] if poll_fn else []

    # auto: fal → pollinations (free) → stability (paid)
    chain: list[tuple[str, GenerateFn]] = []
    if fal_fn:
        chain.append(fal_fn)
    elif mode == "auto":
        logger.warning(
            "FAL_API_KEY not loaded — use quotes in .env: FAL_API_KEY=\"id:secret\""
        )
    if poll_fn:
        chain.append(poll_fn)
    if stability_fn:
        chain.append(stability_fn)
    return chain


async def _generate_with_pollinations(prompt: str, style: str, emotion: str) -> bytes:
    """Free tier via image.pollinations.ai (no API key). Used when fal balance is exhausted."""
    final_prompt = _build_final_prompt(prompt, style, emotion)
    url = f"https://image.pollinations.ai/prompt/{quote(final_prompt)}"
    timeout = httpx.Timeout(connect=30.0, read=180.0, write=30.0, pool=30.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        logger.info("Pollinations request: %s...", final_prompt[:80])
        response = await client.get(url)
    if response.status_code != 200:
        raise RuntimeError(
            f"Pollinations error {response.status_code}: {response.text[:300]}"
        )
    if len(response.content) < 5000:
        raise RuntimeError(
            f"Pollinations returned too little data ({len(response.content)} bytes)"
        )
    ct = (response.headers.get("content-type") or "").lower()
    if "json" in ct or response.content.startswith(b"{"):
        raise RuntimeError(f"Pollinations returned non-image: {response.text[:200]}")
    try:
        return _normalize_png_bytes(response.content)
    except Exception:
        return response.content


async def _generate_with_fal(prompt: str, style: str, emotion: str) -> bytes:
    key = (settings.fal_api_key or "").strip()
    if not key:
        raise RuntimeError("FAL_API_KEY is not set")

    model_id = (settings.fal_model_id or "fal-ai/flux/schnell").strip().lstrip("/")
    final_prompt = _build_final_prompt(prompt, style, emotion)
    payload = {
        "prompt": final_prompt,
        "image_size": "square_hd",
        "num_images": 1,
        "output_format": "png",
        "enable_safety_checker": True,
    }
    headers = {
        "Authorization": f"Key {key}",
        "Content-Type": "application/json",
    }
    timeout = httpx.Timeout(connect=20.0, read=180.0, write=20.0, pool=20.0)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        logger.info("fal.ai request model=%s prompt=%s...", model_id, final_prompt[:80])
        sync_url = f"https://fal.run/{model_id}"
        response = await client.post(sync_url, headers=headers, json=payload)
        if response.status_code == 200:
            data = response.json()
        else:
            logger.warning(
                "fal.run returned %s, trying queue: %s",
                response.status_code,
                response.text[:300],
            )
            data = await _fal_queue_run(client, model_id, headers, payload)

        return await _download_fal_image(client, data)


async def _fal_queue_run(
    client: httpx.AsyncClient,
    model_id: str,
    headers: dict[str, str],
    payload: dict[str, Any],
) -> dict[str, Any]:
    submit_url = f"https://queue.fal.run/{model_id}"
    submit = await client.post(submit_url, headers=headers, json=payload)
    if submit.status_code not in (200, 201, 202):
        detail = submit.text[:500]
        if submit.status_code in (402, 403) and "balance" in detail.lower():
            raise RuntimeError(
                "fal.ai credits exhausted — auto mode will try Pollinations next. "
                "Top up: https://fal.ai/dashboard/billing"
            )
        raise RuntimeError(f"fal.ai queue submit error {submit.status_code}: {detail}")

    body = submit.json()
    request_id = body.get("request_id")
    if not request_id:
        if "images" in body:
            return body
        raise RuntimeError(f"fal.ai queue submit missing request_id: {body!s}"[:300])

    status_url = f"https://queue.fal.run/{model_id}/requests/{request_id}/status"
    result_url = f"https://queue.fal.run/{model_id}/requests/{request_id}"

    for attempt in range(90):
        status_resp = await client.get(status_url, headers=headers)
        if status_resp.status_code != 200:
            raise RuntimeError(
                f"fal.ai queue status error {status_resp.status_code}: {status_resp.text[:300]}"
            )
        status_body = status_resp.json()
        status = (status_body.get("status") or "").upper()
        if status == "COMPLETED":
            result_resp = await client.get(result_url, headers=headers)
            if result_resp.status_code != 200:
                raise RuntimeError(
                    f"fal.ai queue result error {result_resp.status_code}: {result_resp.text[:300]}"
                )
            result = result_resp.json()
            return result.get("response") or result
        if status in ("FAILED", "CANCELLED"):
            raise RuntimeError(f"fal.ai queue {status}: {status_body!s}"[:400])
        await asyncio.sleep(2 if attempt < 5 else 3)

    raise RuntimeError("fal.ai queue timed out waiting for image")


async def _download_fal_image(client: httpx.AsyncClient, data: dict[str, Any]) -> bytes:
    images = data.get("images") or []
    if not images:
        raise RuntimeError(f"fal.ai returned no images: {data!s}"[:300])

    first = images[0]
    image_url = first.get("url")
    if not image_url:
        raise RuntimeError(f"fal.ai image entry missing url: {first!s}"[:200])

    img_resp = await client.get(image_url)
    img_resp.raise_for_status()
    if len(img_resp.content) < 1000:
        raise RuntimeError(f"fal.ai image too small ({len(img_resp.content)} bytes)")

    try:
        return _normalize_png_bytes(img_resp.content)
    except Exception as e:
        logger.warning("fal image normalize failed, using raw bytes: %s", e)
        return img_resp.content


async def _generate_with_stability(prompt: str, style: str, emotion: str) -> bytes:
    await _log_stability_balance_optional()

    headers = {
        "Authorization": f"Bearer {settings.stability_api_key}",
        "Accept": "image/*",
    }
    final_prompt = _build_final_prompt(prompt, style, emotion)
    form: dict[str, str] = {
        "prompt": final_prompt,
        "aspect_ratio": "1:1",
        "output_format": "png",
        "negative_prompt": "blank frame, solid black, empty, void, darkness, underexposed",
        "style_preset": _map_style(style),
    }
    multipart_files = {k: (None, v) for k, v in form.items()}
    api_url = "https://api.stability.ai/v2beta/stable-image/generate/sd3"

    timeout = httpx.Timeout(connect=20.0, read=120.0, write=20.0, pool=20.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        logger.info("Stability API request: %s", api_url)
        response = await client.post(api_url, headers=headers, files=multipart_files)
        if response.status_code == 400 and "style_preset" in form:
            logger.warning("SD3 returned 400; retrying without style_preset")
            form_retry = {k: v for k, v in form.items() if k != "style_preset"}
            multipart_retry = {k: (None, v) for k, v in form_retry.items()}
            response = await client.post(api_url, headers=headers, files=multipart_retry)

    if response.status_code != 200:
        raise RuntimeError(f"Stability AI error {response.status_code}: {response.text[:500]}")

    content_type = (response.headers.get("content-type") or "").lower()
    is_png_bytes = len(response.content) >= 8 and response.content[:8] == b"\x89PNG\r\n\x1a\n"
    if not (content_type.startswith("image/") or is_png_bytes):
        raise RuntimeError(f"Stability returned non-image: {content_type}")

    if response.content.startswith(b"{"):
        raise RuntimeError(f"Stability returned JSON error: {response.text[:200]}")

    if len(response.content) < 1000:
        raise RuntimeError(f"Stability image too small ({len(response.content)} bytes)")

    try:
        return _normalize_png_bytes(response.content)
    except Exception as e:
        logger.warning("Stability PNG normalize failed: %s", e)
        return response.content


async def _log_stability_balance_optional() -> None:
    headers = {
        "Authorization": f"Bearer {settings.stability_api_key}",
        "Accept": "application/json",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                "https://api.stability.ai/v2beta/user/balance",
                headers=headers,
            )
            if response.status_code == 200:
                balance_data = response.json()
                logger.info(
                    "Stability balance OK. credits=%s",
                    balance_data.get("credits", "unknown"),
                )
            else:
                logger.warning(
                    "Stability balance check non-200 (%s), continuing anyway",
                    response.status_code,
                )
        except Exception as e:
            logger.warning("Stability balance check skipped: %s", e)


def _create_fallback_image(output_path: Path, text: str, width: int, height: int) -> None:
    image = Image.new("RGB", (width, height), (240, 245, 250))
    draw = ImageDraw.Draw(image)
    draw.rectangle([(40, 40), (width - 40, height - 40)], outline=(50, 120, 200), width=3)
    draw.multiline_text((70, 90), text, fill=(30, 40, 80), spacing=10)
    image.save(output_path, format="PNG")


def _map_style(style_name: str) -> str:
    style = style_name.lower()
    if "anime" in style:
        return "anime"
    if "cinematic" in style:
        return "cinematic"
    if "digital" in style or "art" in style:
        return "digital-art"
    if "realistic" in style or "photorealistic" in style:
        return "photographic"
    if "fantasy" in style:
        return "fantasy-art"
    if "3d" in style:
        return "3d-model"
    if "comic" in style:
        return "comic-book"
    if "isometric" in style:
        return "isometric"
    if "line" in style:
        return "line-art"
    if "pixel" in style:
        return "pixel-art"
    return "digital-art"


async def test_image_generation() -> None:
    output_path = Path("test_image.png")
    await generate_image_file(
        "A red rose in a garden",
        "realistic",
        "beautiful",
        output_path,
    )
    if output_path.exists():
        print(f"OK: {output_path} ({output_path.stat().st_size} bytes)")
    else:
        print("FAIL: output not created")
