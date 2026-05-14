import io
import logging
from pathlib import Path

import httpx
from PIL import Image, ImageDraw

from app.core.config import settings

logger = logging.getLogger(__name__)


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
    """Decode API PNG, flatten alpha, re-encode so clients and video pipeline see correct colors."""
    with Image.open(io.BytesIO(raw)) as decoded:
        rgb = pil_image_to_rgb_opaque(decoded)
        out = io.BytesIO()
        rgb.save(out, format="PNG")
        return out.getvalue()


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
    # First, validate the API key by checking account balance
    await _validate_api_key()
    
    # SD3 stable-image expects multipart or url-encoded form fields (see Stability docs / examples).
    # Sending JSON alone can return 200 with an empty or incorrect render for some accounts.
    headers = {
        "Authorization": f"Bearer {settings.stability_api_key}",
        "Accept": "image/png",
    }
    final_prompt = f"{prompt}. Mood: {emotion}. Style: {style}."
    form: dict[str, str] = {
        "prompt": final_prompt,
        "aspect_ratio": "1:1",
        "output_format": "png",
        "negative_prompt": "blank frame, solid black, empty, void, darkness, underexposed",
        "style_preset": _map_style(style),
    }

    api_url = "https://api.stability.ai/v2beta/stable-image/generate/sd3"

    timeout = httpx.Timeout(connect=20.0, read=120.0, write=20.0, pool=20.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            logger.info(f"Making Stability API request to {api_url}")
            logger.info(f"Prompt: {final_prompt[:100]}...")
            response = await client.post(
                api_url,
                headers=headers,
                data=form,
            )
            logger.info(f"Stability API response status: {response.status_code}")
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
            logger.error(f"{error_msg} - Response: {error_detail}")
        except:
            pass
        raise RuntimeError(error_msg)
    
    # Check if response content is actually an image
    content_type = response.headers.get('content-type', '')
    logger.info(f"Response content-type: {content_type}")
    logger.info(f"Response content length: {len(response.content)}")
    
    if not content_type.startswith('image/'):
        logger.error(f"Unexpected content-type: {content_type}")
        logger.error(f"Response text: {response.text[:500]}")
        raise RuntimeError(f"API returned non-image content: {content_type}")
    
    if response.content.startswith(b"{"):
        error_json = response.content.decode("utf-8", errors="ignore")
        logger.error(f"API returned JSON instead of image: {error_json[:500]}")
        debug_file = Path("debug_api_response.json")
        debug_file.write_text(error_json)
        logger.error(f"Saved error response to {debug_file}")
        raise RuntimeError(f"API returned error JSON instead of image: {error_json[:200]}")
    # Check minimum image size (PNG header is ~100 bytes, but real images are much larger)
    if len(response.content) < 1000:
        logger.error(f"Image too small: {len(response.content)} bytes")
        logger.error(f"Content preview: {response.content[:200]}")
        # Save the small response for debugging
        debug_file = Path("debug_small_response.bin")
        debug_file.write_bytes(response.content)
        logger.error(f"Saved small response to {debug_file}")
        raise RuntimeError(f"API returned invalid image data (too small: {len(response.content)} bytes)")

    try:
        return _normalize_png_bytes(response.content)
    except Exception as e:
        logger.error(f"PNG normalize failed, returning raw bytes: {e}", exc_info=True)
        return response.content


async def _validate_api_key():
    """Validate the API key by checking account balance"""
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
                logger.info(f"API Key valid. Credits: {balance_data.get('credits', 'unknown')}")
                return True
            else:
                logger.error(f"API Key validation failed: {response.status_code} - {response.text}")
                raise RuntimeError(f"Invalid API key: {response.text}")
        except Exception as e:
            logger.error(f"API Key validation error: {str(e)}")
            raise RuntimeError(f"API Key validation failed: {str(e)}")


def _create_fallback_image(output_path: Path, text: str, width: int, height: int) -> None:
    image = Image.new("RGB", (width, height), (240, 245, 250))  # Light blue background instead of black
    draw = ImageDraw.Draw(image)
    draw.rectangle([(40, 40), (width - 40, height - 40)], outline=(50, 120, 200), width=3)
    draw.multiline_text((70, 90), text, fill=(30, 40, 80), spacing=10)
    image.save(output_path, format="PNG")


def _map_style(style_name: str) -> str:
    style = style_name.lower()
    # Stability AI core model supported style presets
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
    # Default to digital-art if no match
    return "digital-art"


async def test_image_generation():
    """Test function to debug image generation"""
    import asyncio
    from pathlib import Path
    
    # Test with a simple prompt
    test_prompt = "A red rose in a garden"
    test_style = "realistic"
    test_emotion = "beautiful"
    
    output_path = Path("test_image.png")
    
    try:
        await generate_image_file(test_prompt, test_style, test_emotion, output_path)
        print(f"✅ Image generated successfully at {output_path}")
        
        # Check if file exists and has content
        if output_path.exists():
            size = output_path.stat().st_size
            print(f"File size: {size} bytes")
            
            # Try to open with PIL to verify it's a valid image
            from PIL import Image
            with Image.open(output_path) as img:
                print(f"Image dimensions: {img.size}")
                print(f"Image mode: {img.mode}")
                
                # Check if image is mostly black
                if img.mode == 'RGB':
                    pixels = list(img.getdata())
                    avg_color = tuple(sum(c) // len(pixels) for c in zip(*pixels))
                    print(f"Average color: {avg_color}")
                    
                    if all(c < 10 for c in avg_color):  # Very dark
                        print("❌ Image appears to be black/dark!")
                    else:
                        print("✅ Image has proper colors!")
        else:
            print("❌ Output file was not created")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
