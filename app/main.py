from datetime import datetime
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes.auth import router as auth_router
from app.api.routes.generation import router as generation_router
from app.api.routes.projects import router as projects_router
from app.core.config import settings
from app.firestore_db import init_firestore
from app.services.storage import MEDIA_ROOT, ensure_media_dirs

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


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
app.include_router(auth_router)
app.include_router(generation_router)
app.include_router(projects_router)


@app.on_event("startup")
def startup() -> None:
    ensure_media_dirs()
    if not settings.skip_firestore_startup:
        init_firestore()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@app.exception_handler(Exception)
async def generic_error_handler(_, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": f"Server error: {str(exc)}"})
