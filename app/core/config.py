from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Easemovie-backend root (parent of `app/`)
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    app_name: str = "Easemovie Backend"
    host: str = "0.0.0.0"
    port: int = 8000
    media_root: str = "media"
    stability_api_key: str = ""
    stability_base_url: str = "https://api.stability.ai/v2beta/stable-image/generate/core"

    # Firebase Admin SDK JSON path (relative to BACKEND_ROOT or absolute)
    firebase_credentials_path: str = ""
    firestore_projects_collection: str = "projects"
    # Set SKIP_FIRESTORE_STARTUP=true for pytest / local runs without Firebase credentials.
    skip_firestore_startup: bool = Field(default=False)

    model_config = SettingsConfigDict(
        env_file=(".env", "app/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
