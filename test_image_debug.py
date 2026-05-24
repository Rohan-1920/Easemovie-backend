import asyncio
import sys
import os
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "app"))

from app.services.image_generation import test_image_generation

if __name__ == "__main__":
    print("Testing image generation...")
    asyncio.run(test_image_generation())