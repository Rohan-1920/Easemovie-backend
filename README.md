# Easemovie Backend

Backend service for **Easemovie**: turn a story into scenes, generate images per scene, build video, add narration, and optionally save project metadata. Built with **FastAPI** (Python).

---

## What’s inside this backend

| Capability | What it does |
|------------|----------------|
| **Story → scenes** | Splits user text into ordered scenes with simple mood/camera hints. |
| **Scene images** | Calls **Stability AI** when configured; otherwise generates a simple local PNG so the API never breaks. |
| **Video (legacy)** | Builds an MP4 from **text slides** — matches older app flows that send scene text only. |
| **Video from images** | Builds an MP4 **slideshow** from a list of image URLs (your generated scene art). |
| **Voice** | Creates **MP3 narration** using **Edge TTS** (needs internet). |
| **Short film** | **`compose_film`** stitches slideshow + voice into **one final MP4** via FFmpeg. |
| **Projects** | **`/projects`** saves to **Firebase Firestore**: titles, media URLs, scene lines — aligns with the Easemovie Android client. |
| **Static files** | Serves generated assets under **`/media`** (images, videos, audio). |

**Architecture & diagrams:** [ARCHITECTURE.md](./ARCHITECTURE.md)

---

## How it works (high level)

1. Client sends story text → **`POST /segment`** → gets a list of scenes (text + mood + camera).
2. For each scene, client calls **`POST /generate_image`** (with style/emotion) → gets **`image_path`** URLs hosted by this server under `/media/images/`.
3. To make a narrated clip, client calls **`POST /compose_film`** with those **`image_urls`** plus either **`narration_text`** or **`scene_narrations`** (same count as images).
4. Response contains **`video_url`** — open it in a browser or pass it to the mobile player.

**Legacy path:** **`POST /generate_video`** still builds video from **scene text only** (no images), for compatibility.

---

## Tech you should know

- **Python 3.10+**, **FastAPI**, **Uvicorn**
- **Stability AI** (HTTP) for images when `STABILITY_API_KEY` is set
- **edge-tts** for speech (internet required)
- **FFmpeg** via **`imageio-ffmpeg`** (bundled)
- **Firebase Admin SDK + Firestore** for `/projects` (service-account JSON)

---

## Prerequisites

- Python **3.10+**
- **Internet** (images API + TTS)
- Android testing: phone/emulator must reach this machine’s IP/port

---

## Setup

```bash
cd Easemovie-backend
python -m venv .venv
```

**Windows:** `.\.venv\Scripts\Activate.ps1`  
**macOS / Linux:** `source .venv/bin/activate`

```bash
pip install -r requirements.txt
```

Copy `.env.example` → `.env` and fill values:

| Variable | Purpose |
|----------|---------|
| `FIREBASE_CREDENTIALS_PATH` | Firebase Admin SDK JSON path (repo root or absolute). Required for **`/projects`**. |
| `FIRESTORE_PROJECTS_COLLECTION` | Firestore collection (default `projects`). Match your Android app. |
| `STABILITY_API_KEY` | Optional; empty = local fallback images. |
| `SKIP_FIRESTORE_STARTUP` | Set `true` only for **`pytest`** without credentials (see tests). |
| `MEDIA_ROOT` | Generated media folder (default `media`). |

---

## Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- API: http://127.0.0.1:8000  
- Swagger: http://127.0.0.1:8000/docs  

---

## `scripts/demo_short_film.py`

Optional **end-to-end demo** (not used by production code): calls **`/segment`** → **`/generate_image`** per scene → **`/compose_film`**, prints one **`video_url`**.

```bash
python scripts/demo_short_film.py
# Optional: $env:EASEMOVIE_BASE = "http://127.0.0.1:8001"
```

---

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

`tests/conftest.py` sets **`SKIP_FIRESTORE_STARTUP=true`** so **`/health`** and **`/segment`** run without Firebase.

---

## Android `BASE_URL`

| Setup | URL |
|-------|-----|
| Emulator → PC | `http://10.0.2.2:8000/` |
| Phone (same Wi‑Fi) | `http://<PC_LAN_IP>:8000/` |

---

## Related docs

- [ARCHITECTURE.md](./ARCHITECTURE.md)
