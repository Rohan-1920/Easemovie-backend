from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Easemovie-backend root (parent of `app/`)
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    app_name: str = "Easemovie Backend"
    host: str = "0.0.0.0"
    port: int = 8000
    media_root: str = "media"
    stability_api_key: str = ""
    stability_base_url: str = "https://api.stability.ai/v2beta/stable-image/generate/ultra"

    @field_validator("stability_api_key", mode="before")
    @classmethod
    def strip_stability_key(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().strip('"').strip("'")
        return v

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
