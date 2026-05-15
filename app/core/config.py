from pathlib import Path

import os

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Easemovie-backend root (parent of `app/`)
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    app_name: str = "Easemovie Backend"
    host: str = "0.0.0.0"
    port: int = 8000
    media_root: str = "media"
    # Image generation: auto (default) | fal | stability
    image_provider: str = "auto"
    # Env: FAL_API_KEY — use quotes in .env if the key contains ':' (fal format id:secret)
    fal_api_key: str = ""
    fal_model_id: str = "fal-ai/flux/schnell"
    # Free fallback when fal/stability fail (no API key required for image.pollinations.ai).
    pollinations_fallback_enabled: bool = True
    # If false, API returns 500 instead of a placeholder PNG when all providers fail.
    image_allow_placeholder_fallback: bool = False
    stability_api_key: str = ""
    stability_base_url: str = "https://api.stability.ai/v2beta/stable-image/generate/ultra"

    @field_validator("stability_api_key", "fal_api_key", mode="before")
    @classmethod
    def strip_api_keys(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().strip('"').strip("'")
        return v

    @field_validator("image_provider", mode="before")
    @classmethod
    def normalize_image_provider(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @model_validator(mode="after")
    def fill_fal_key_from_env(self) -> "Settings":
        """Support FAL_KEY and fix keys that dotenv dropped (must be quoted in .env if they contain ':')."""
        if not self.fal_api_key:
            self.fal_api_key = (
                os.getenv("FAL_API_KEY", "").strip().strip('"').strip("'")
                or os.getenv("FAL_KEY", "").strip().strip('"').strip("'")
            )
        return self

    # Firebase Admin SDK JSON path (relative to BACKEND_ROOT or absolute)
    firebase_credentials_path: str = ""
    firestore_projects_collection: str = "projects"
    firestore_users_collection: str = "users"
    # Set SKIP_FIRESTORE_STARTUP=true for pytest / local runs without Firebase credentials.
    skip_firestore_startup: bool = Field(default=False)
    jwt_secret_key: str = "your-secret-key-here"  # Change in production
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24

    model_config = SettingsConfigDict(
        # Resolve from repo root so the key loads even if uvicorn cwd is not Easemovie-backend/
        env_file=(
            str(BACKEND_ROOT / ".env"),
            str(BACKEND_ROOT / "app" / ".env"),
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
