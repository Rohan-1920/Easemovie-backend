# Easemovie Backend — Architecture

## Storage model

| Data | Where it lives |
|------|----------------|
| Generated images / videos / audio | Local **`media/`** (served under **`/media`**) |
| Project records (`/projects`) | **Google Cloud Firestore** via Firebase Admin SDK |
| Configuration | `.env` (never commit secrets) |

**Admin SDK** bypasses client Firestore rules — protect the JSON key file and run the API only on trusted servers.

## Module map

- **`app/main.py`** — FastAPI app, CORS, static mount, startup (**`init_firestore`** skipped when **`SKIP_FIRESTORE_STARTUP=true`**, e.g. pytest)
- **`app/api/routes/generation.py`** — AI/video/voice endpoints
- **`app/api/routes/projects.py`** — CRUD → **`firestore_db`**
- **`app/firestore_db.py`** — Firebase init + Firestore CRUD for collection `settings.firestore_projects_collection`
- **`app/services/*`** — segmentation, Stability images, slideshow video, Edge TTS, FFmpeg mux
- **`app/core/config.py`** — env settings + **`BACKEND_ROOT`**

## Automated tests

- **`tests/`** — `pytest` suite; **`tests/conftest.py`** sets **`SKIP_FIRESTORE_STARTUP=true`** so tests run without Firebase credentials.
- **`requirements-dev.txt`** — installs **`pytest`** (`pip install -r requirements-dev.txt`).

## Short-film sequence

See README “How it works”. Compose uses FFmpeg to mux slideshow MP4 + narration MP3.

## Firestore document shape (`projects`)

Each document ID is a **string** (auto-generated). Fields align with `ProjectCreate`:

- `user_id`, `title`, `style`, `video_url`, `thumbnail_url`, `scenes` (array), `created_at` (server timestamp)

Android clients writing to the same **`projects`** collection will see documents created by this backend.
