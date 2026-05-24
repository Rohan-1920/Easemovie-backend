import logging
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes.generation import router as generation_router
from app.api.routes.projects import router as projects_router
from app.core.config import settings
from app.core.startup_checks import is_valid_replicate_token, run_startup_checks
from app.firestore_db import init_firestore
from app.services.storage import MEDIA_ROOT, ensure_media_dirs


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title=settings.app_name,
    version="1.2.0",
    description="Modular backend API for Easemovie story-to-animation workflow.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Ensure media directories exist before mounting StaticFiles.
ensure_media_dirs()
app.mount("/media", StaticFiles(directory=str(MEDIA_ROOT)), name="media")
app.include_router(generation_router)
app.include_router(projects_router)


@app.on_event("startup")
def startup() -> None:
    ensure_media_dirs()
    run_startup_checks()
    if not settings.skip_firestore_startup:
        init_firestore()


@app.get("/health")
def health() -> dict:
    s = settings
    return {
        "status": "ok",
        "time": datetime.utcnow().isoformat(),
        "config": {
            "image_model": s.image_model,
            "video_model": s.video_model,
            "image_token_set": bool(s.image_token()),
            "video_token_set": bool(s.video_token()),
            "image_token_valid": is_valid_replicate_token(s.image_token()),
            "video_token_valid": is_valid_replicate_token(s.video_token()),
            "public_base_url": (s.public_base_url or "").strip() or None,
            "allow_ai_fallback": s.allow_ai_fallback,
        },
    }


@app.exception_handler(Exception)
async def generic_error_handler(_, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": f"Server error: {str(exc)}"})
