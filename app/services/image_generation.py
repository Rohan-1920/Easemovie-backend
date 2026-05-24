"""Image generation — delegates to configured image model provider."""

from pathlib import Path

from app.providers.image_model import generate_image_file

__all__ = ["generate_image_file"]
