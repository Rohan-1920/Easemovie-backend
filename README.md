# Easemovie Backend

Story → scenes → **FLUX Dev** images → **Stable Video Diffusion** clips → voice + Firestore. FastAPI (Python).

---

## AI models (Replicate)

| Purpose | Model | Env token |
|---------|--------|-----------|
| **Images** | `black-forest-labs/flux-dev` | `IMAGE_REPLICATE_API_TOKEN` |
| **Video** | `sunfjun/stable-video-diffusion` | `VIDEO_REPLICATE_API_TOKEN` |

Video model is **image-to-video**: pehle scene image generate karo, phir us URL se video banegi.

Optional: same account ho to `REPLICATE_API_TOKEN` dono ke fallback ke liye.

| Variable | Default |
|----------|---------|
| `IMAGE_MODEL` | `black-forest-labs/flux-dev` |
| `VIDEO_MODEL` | `sunfjun/stable-video-diffusion` |

Check: `GET /health` → `config.image_token_set`, `config.video_token_set`

**Architecture:** [ARCHITECTURE.md](./ARCHITECTURE.md)

---

## Setup

```bash
cd Easemovie-backend
python -m venv .venv
```

Windows: `.\.venv\Scripts\Activate.ps1` · macOS/Linux: `source .venv/bin/activate`

```bash
pip install -r requirements.txt
copy .env.example .env
```

Copy **`.env.example` → `.env`** and fill in:

```env
IMAGE_REPLICATE_API_TOKEN=r8_xxxx
VIDEO_REPLICATE_API_TOKEN=r8_yyyy
IMAGE_MODEL=black-forest-labs/flux-dev
VIDEO_MODEL=sunfjun/stable-video-diffusion
PUBLIC_BASE_URL=http://YOUR_PC_LAN_IP:8000
ALLOW_AI_FALLBACK=true
```

**`PUBLIC_BASE_URL`** is required for reliable **video** generation (Replicate must read your scene images). Use your PC IPv4 from `ipconfig`, not `127.0.0.1`.

On server start, check terminal logs for configuration warnings.  
`GET /health` → `config.image_token_set`, `video_token_set`, `public_base_url`.

Tokens: [replicate.com/account/api-tokens](https://replicate.com/account/api-tokens)

---

## Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- http://127.0.0.1:8000/docs  
- http://127.0.0.1:8000/health  

---

## Flow

1. `POST /segment` — story → scenes  
2. `POST /generate_image` — FLUX Dev per scene  
3. `POST /generate_video_from_images` or `/compose_film` — SVD animates first image (or slideshow fallback)  
4. `POST /generate_voice` — Edge TTS (optional)  

---

## Demo & tests

```bash
python scripts/demo_short_film.py
pip install -r requirements-dev.txt && pytest
```

---

## Android

| Setup | URL |
|-------|-----|
| Emulator | `http://10.0.2.2:8000/` |
| Phone | `http://<PC_LAN_IP>:8000/` |
