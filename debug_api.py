import asyncio
import os

import httpx


async def test_api() -> None:
    api_key = os.environ.get("STABILITY_API_KEY", "")
    if not api_key:
        print("Set STABILITY_API_KEY in the environment first.")
        return

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "image/*",
    }

    payload = {
        "prompt": "A beautiful sunset over mountains. Mood: peaceful. Style: cinematic.",
        "aspect_ratio": "1:1",
        "output_format": "png",
    }

    url = "https://api.stability.ai/v2beta/stable-image/generate/sd3"

    print(f"Testing API call to: {url}")
    print("Payload keys:", list(payload.keys()))

    multipart = {k: (None, v) for k, v in payload.items()}

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, headers=headers, files=multipart)
            print(f"Status: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type')}")
            print(f"Content-Length: {len(response.content)}")

            if response.status_code == 200:
                ct = response.headers.get("content-type", "")
                is_png = len(response.content) >= 8 and response.content[:8] == b"\x89PNG\r\n\x1a\n"
                if ct.startswith("image/") or is_png:
                    print("API returned image bytes")
                    with open("test_image.png", "wb") as f:
                        f.write(response.content)
                    print("Saved test_image.png")
                else:
                    print("Non-image content")
                    print(response.text[:500])
            else:
                print(f"API Error: {response.text[:500]}")

        except Exception as e:
            print(f"Connection Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_api())
