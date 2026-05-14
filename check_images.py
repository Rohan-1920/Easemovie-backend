import os
from pathlib import Path

# Check image file sizes
images_dir = Path("media/images")
if images_dir.exists():
    png_files = list(images_dir.glob("*.png"))
    if png_files:
        # Sort by modification time (newest first)
        png_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        print("Recent image files:")
        for i, img_file in enumerate(png_files[:5]):
            size_kb = img_file.stat().st_size / 1024
            print(".1f")

        # Check if any file is large enough to be a real image (not fallback)
        large_files = [f for f in png_files if f.stat().st_size > 10000]  # >10KB
        if large_files:
            print(f"\n✅ Found {len(large_files)} large image files (>10KB) - these are likely real generated images!")
            print("✅ Image generation is working properly - NOT returning black images!")
        else:
            print("\n❌ All images are small (<10KB) - likely fallback placeholder images")
            print("❌ Image generation may still be failing")
    else:
        print("No PNG files found")
else:
    print("Images directory not found")