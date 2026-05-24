from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    app_name: str = "Easemovie Backend"
    host: str = "0.0.0.0"
    port: int = 8000
    media_root: str = "media"

    # --- Replicate: two API tokens (recommended) ---
    image_replicate_api_token: str = ""
    video_replicate_api_token: str = ""
    replicate_api_token: str = ""  # fallback if per-model tokens not set

    image_model: str = "black-forest-labs/flux-dev"
    video_model: str = "sunfjun/stable-video-diffusion"

    # Kling image-to-video (optional — expensive; set VIDEO_MODEL in .env)
    kling_duration: int = 5  # 5 or 10 seconds
    kling_aspect_ratio: str = "16:9"
    kling_negative_prompt: str = "blur, distort, low quality, static, frozen, no motion"

    # Public URL of this API (LAN IP for phone/emulator). Replicate must reach scene images for video.
    # Example: http://192.168.1.20:8000
    public_base_url: str = ""

    # FLUX Dev defaults
    flux_aspect_ratio: str = "16:9"
    flux_output_format: str = "png"
    flux_num_inference_steps: int = 28
    flux_guidance: float = 3.5

    # Stable Video Diffusion (sunfjun) — budget-friendly ~$0.04/run on Replicate
    svd_video_length: str = "14_frames_with_svd"  # cheaper than 25_frames_with_svd_xt
    svd_frames_per_second: int = 6
    svd_motion_bucket_id: int = 180  # higher = more visible motion (127–255)
    svd_cond_aug: float = 0.02
    svd_decoding_t: int = 8  # lower = faster/cheaper (min quality tradeoff)

    replicate_poll_interval_seconds: float = 2.0
    replicate_poll_timeout_seconds: float = 900.0

    # If true: missing API / failed Replicate → placeholder image or slideshow (no crash)
    allow_ai_fallback: bool = True

    firebase_credentials_path: str = ""
    firestore_projects_collection: str = "projects"
    skip_firestore_startup: bool = Field(default=False)

    model_config = SettingsConfigDict(
        env_file=(".env", "app/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def image_token(self) -> str:
        return (
            (self.image_replicate_api_token or "").strip()
            or (self.replicate_api_token or "").strip()
        )

    def video_token(self) -> str:
        return (
            (self.video_replicate_api_token or "").strip()
            or (self.replicate_api_token or "").strip()
        )

    def api_base_url(self, request_base: str = "") -> str:
        """URL returned to clients and used when building /media links."""
        public = (self.public_base_url or "").strip().rstrip("/")
        if public:
            return public
        return (request_base or "").strip().rstrip("/")


settings = Settings()
