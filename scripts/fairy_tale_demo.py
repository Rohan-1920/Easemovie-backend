"""
Fairy tale film demo: segment -> generate_image per scene -> compose_film (voice).

Start the backend first:
  uvicorn app.main:app --host 0.0.0.0 --port 8000

Then run:
  python scripts/fairy_tale_demo.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request


BASE = os.environ.get("EASEMOVIE_BASE", "http://127.0.0.1:8000")


def _post_json(path: str, body: dict) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post_generate_image(text: str, style: str, emotion: str) -> str:
    from urllib.parse import quote

    q = f"?text={quote(text)}&style={quote(style)}&emotion={quote(emotion)}"
    req = urllib.request.Request(f"{BASE}/generate_image{q}", method="POST")
    with urllib.request.urlopen(req, timeout=300) as resp:
        out = json.loads(resp.read().decode("utf-8"))
    return out["image_path"]


def main() -> int:
    story = (
        "Once upon a time, in a magical forest, there lived a little fairy named Lila. "
        "She had sparkling wings and a heart full of kindness. "
        "One sunny morning, Lila found a lost baby bird crying on the ground. "
        "With gentle hands, she picked it up and sang a lullaby to calm it. "
        "The bird's mother soon returned, and Lila helped reunite them. "
        "Grateful, the birds taught Lila to fly higher than ever. "
        "From that day, Lila became the guardian of the forest, spreading joy and magic everywhere. "
        "And they all lived happily ever after."
    )
    style = "Whimsical"

    print("1) Health...")
    try:
        with urllib.request.urlopen(f"{BASE}/health", timeout=5) as r:
            print(r.read().decode())
    except urllib.error.URLError as e:
        print(f"Backend not reachable: {e}", file=sys.stderr)
        print("Start it with: uvicorn app.main:app --host 0.0.0.0 --port 8000", file=sys.stderr)
        return 1

    print("2) Segment...")
    seg = _post_json("/segment", {"text": story})
    scenes = seg["scenes"]
    print(json.dumps(seg, indent=2))

    print("3) Images (per scene)...")
    urls: list[str] = []
    for sc in scenes:
        mood = sc.get("mood") or "joyful"
        txt = sc.get("text") or story
        prompt = f"{txt} — camera: {sc.get('camera','wide shot')}"
        print(f"   scene {sc['index']}: generating...")
        img_url = _post_generate_image(prompt, style, mood)
        urls.append(img_url)
        print(f"   -> {img_url}")
        time.sleep(1)  # Slow down to avoid rate limits

    narrations = [sc["text"] for sc in scenes]

    print("4) Compose film (voice + images)...")
    film = _post_json(
        "/compose_film",
        {
            "image_urls": urls,
            "seconds_per_scene": 4.0,
            "scene_narrations": narrations,
            "voice": "en-US-JennyNeural",
        },
    )
    print("\n=== FINAL FAIRY TALE VIDEO ===")
    print(json.dumps(film, indent=2))
    print("\nOpen this URL in your browser to watch the fairy tale video:", film["video_url"])


if __name__ == "__main__":
    sys.exit(main())