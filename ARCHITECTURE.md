# Architecture

## AI models

```
IMAGE_REPLICATE_API_TOKEN  →  black-forest-labs/flux-dev     →  POST /generate_image
VIDEO_REPLICATE_API_TOKEN  →  sunfjun/stable-video-diffusion →  POST /generate_video*
                                                                  (needs input_image URL)
```

- **FLUX Dev:** text → PNG (`prompt`, `aspect_ratio`, `output_format=png`, …)  
- **Stable Video Diffusion:** `input_image` URL → MP4 (`video_length`, `frames_per_second`, …)  
- Fallback: PIL placeholder (image), FFmpeg slideshow (video) if API fails or tokens missing  

## Storage

| Data | Where |
|------|--------|
| Media files | `media/` → `/media` |
| Projects | Firestore |

## Code layout

- `app/providers/replicate_api.py` — HTTP + polling  
- `app/providers/image_model.py` — FLUX  
- `app/providers/video_model.py` — SVD  
- `app/services/video_slideshow.py` — fallback slideshow  
