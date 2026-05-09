"""
Short film demo: segment -> generate_image per scene -> compose_film (voice).

Pehle backend chalao:
  uvicorn app.main:app --host 0.0.0.0 --port 8000

Phir:
  python scripts/demo_short_film.py
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
        "An astronaut lands on a silent alien planet. "
        "Crystal towers glow under twin moons. "
        "A storm rises and she finds shelter in an ancient hall."
    )
    style = "Cinematic"

    print("1) Health...")
    try:
        with urllib.request.urlopen(f"{BASE}/health", timeout=5) as r:
            print(r.read().decode())
    except urllib.error.URLError as e:
        print(f"Backend reachable nahi: {e}", file=sys.stderr)
        print(f"Pehle run karo: uvicorn app.main:app --host 0.0.0.0 --port 8000", file=sys.stderr)
        return 1

    print("2) Segment...")
    seg = _post_json("/segment", {"text": story})
    scenes = seg["scenes"]
    print(json.dumps(seg, indent=2))

    print("3) Images (har scene)...")
    urls: list[str] = []
    for sc in scenes[:5]:
        mood = sc.get("mood") or "neutral"
        txt = sc.get("text") or story
        prompt = f"{txt} — camera: {sc.get('camera','wide shot')}"
        print(f"   scene {sc['index']}: generating...")
        img_url = _post_generate_image(prompt, style, mood)
        urls.append(img_url)
        print(f"   -> {img_url}")
        time.sleep(0.3)

    narrations = [
        "Scene one: the astronaut touches down on a silent world.",
        "Scene two: alien crystal towers shine under two moons.",
        "Scene three: a storm breaks as she runs into ancient shelter.",
    ]
    while len(narrations) < len(urls):
        narrations.append(narrations[-1])

    print("4) Compose film (voice + images)...")
    film = _post_json(
        "/compose_film",
        {
            "image_urls": urls,
            "seconds_per_scene": 4.0,
            "scene_narrations": narrations[: len(urls)],
            "voice": "en-US-JennyNeural",
        },
    )
    print("\n=== FINAL SAMPLE ===")
    print(json.dumps(film, indent=2))
    print("\nBrowser mein video kholo:", film["video_url"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
