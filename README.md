# Easemovie Backend

Story → scenes → **FLUX Dev** images → **Stable Video Diffusion** clips → **ElevenLabs** voice + Firestore. FastAPI (Python).

---

## AI models

| Purpose | Model | Env token |
|---------|--------|-----------|
| **Images** | `black-forest-labs/flux-dev` | `IMAGE_REPLICATE_API_TOKEN` |
| **Video** | `sunfjun/stable-video-diffusion` | `VIDEO_REPLICATE_API_TOKEN` |
| **Voice** | ElevenLabs `eleven_flash_v2_5` | `ELEVENLABS_API_KEY` |

Video model is **image-to-video**: pehle scene image generate karo, phir us URL se video banegi.

Voice **`auto`** hai by default — story type + mood ke hisaab se ElevenLabs voice select hoti hai. Key na ho to Edge TTS fallback.

| Variable | Default |
|----------|---------|
| `IMAGE_MODEL` | `black-forest-labs/flux-dev` |
| `VIDEO_MODEL` | `sunfjun/stable-video-diffusion` |
| `ELEVENLABS_MODEL` | `eleven_flash_v2_5` |

Check: `GET /health` → `config.elevenlabs_key_valid`, `config.voice_mode`

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
copy .env.example app\.env
```

**Main config file:** `app/.env` — yahan saari keys rakho.

```env
IMAGE_REPLICATE_API_TOKEN=r8_xxxx
VIDEO_REPLICATE_API_TOKEN=r8_yyyy
PUBLIC_BASE_URL=http://YOUR_PC_LAN_IP:8000

# ElevenLabs — story voice (auto mood selection)
ELEVENLABS_API_KEY=sk_your_key_here
ELEVENLABS_MODEL=eleven_flash_v2_5
```

**`PUBLIC_BASE_URL`** is required for reliable **video** generation (Replicate must read your scene images). Use your PC IPv4 from `ipconfig`, not `127.0.0.1`.

ElevenLabs key: [elevenlabs.io/app/settings/api-keys](https://elevenlabs.io/app/settings/api-keys)

On server start, check terminal logs for configuration warnings.  
`GET /health` → tokens + `voice_mode: elevenlabs` or `edge_fallback`.

Replicate tokens: [replicate.com/account/api-tokens](https://replicate.com/account/api-tokens)

---

## Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- http://127.0.0.1:8000/docs  
- http://127.0.0.1:8000/health  

---

## API flow

1. `POST /segment` — story → scenes (+ `mood`, recommended `voice` per scene)
2. `POST /generate_image` — FLUX Dev per scene
3. `POST /compose_film?async_mode=true` — returns **`job_id` immediately** (no Render timeout)
4. `GET /jobs/{job_id}` — poll until `status=completed`, then read `result.video_url`
5. Or blocking: `POST /compose_film?async_mode=false` (local dev only)

**4 scenes @ 25 frames / 5 fps ≈ 20 second animated film** (see `SVD_*` in `app/.env`).

Firestore projects saved from backend use **Android-compatible field names** (`userId`, `videoUrl`, `createdAt`).

---

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

---

## Android

| Setup | URL |
|-------|-----|
| Emulator | `http://10.0.2.2:8000/` |
| Phone | `http://<PC_LAN_IP>:8000/` |
