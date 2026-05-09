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

**Architecture:** [ARCHITECTURE.md](./ARCHITECTURE.md)

---

## How it works (high level)

1. **`POST /segment`** — story → scenes (+ mood/camera hints).
2. **`POST /generate_image`** per scene → **`image_path`** URLs under `/media/images/`.
3. **`POST /compose_film`** with **`image_urls`** + **`narration_text`** or **`scene_narrations`** → **`video_url`**.
4. Legacy: **`POST /generate_video`** builds MP4 from scene text only (no images).

---

## Tech

Python **3.10+**, FastAPI, Uvicorn, Stability AI (optional), edge-tts, FFmpeg (via imageio-ffmpeg), Firebase Admin + Firestore for **`/projects`**.

---

## Setup

```bash
cd Easemovie-backend
python -m venv .venv
```

Windows: `.\.venv\Scripts\Activate.ps1` · macOS/Linux: `source .venv/bin/activate`

```bash
pip install -r requirements.txt
copy .env.example .env   # then edit .env
```

| Variable | Purpose |
|----------|---------|
| `FIREBASE_CREDENTIALS_PATH` | Admin SDK JSON (needed for **`/projects`**). |
| `FIRESTORE_PROJECTS_COLLECTION` | Collection name (default `projects`). |
| `STABILITY_API_KEY` | Optional; empty → fallback PNG images. |
| `SKIP_FIRESTORE_STARTUP` | Use `true` only when running **`pytest`** without Firebase (`tests/conftest.py` sets this). |

---

## Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- http://127.0.0.1:8000/docs — Swagger  
- http://127.0.0.1:8000/health — health  

---

## Demo script

**`scripts/demo_short_film.py`** — optional smoke test (not used in production): runs **`/segment`** → **`/generate_image`** → **`/compose_film`** and prints one **`video_url`**.

```bash
python scripts/demo_short_film.py
```

Optional: `EASEMOVIE_BASE=http://127.0.0.1:8001` if not port 8000.

---

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

---

## Android `BASE_URL`

| Setup | URL |
|-------|-----|
| Emulator | `http://10.0.2.2:8000/` |
| Phone (same Wi‑Fi) | `http://<PC_LAN_IP>:8000/` |
