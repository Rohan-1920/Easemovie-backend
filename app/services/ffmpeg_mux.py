from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import imageio_ffmpeg


def ffmpeg_exe() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def mux_video_audio(video_path: str, audio_path: str, out_path: str) -> None:
    cmd = [
        ffmpeg_exe(),
        "-y",
        "-i",
        video_path,
        "-i",
        audio_path,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        out_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg mux failed: {result.stderr}")


def concat_mp3_files(paths: list[str], output_mp3: str) -> None:
    if not paths:
        raise ValueError("No audio clips to concat.")
    out = Path(output_mp3)
    out.parent.mkdir(parents=True, exist_ok=True)
    if len(paths) == 1:
        shutil.copy2(paths[0], output_mp3)
        return

    list_path = out.with_suffix(".concat.txt")
    lines: list[str] = []
    for raw in paths:
        ap = Path(raw).resolve().as_posix()
        lines.append(f"file '{ap}'")
    list_path.write_text("\n".join(lines), encoding="utf-8")

    cmd = [
        ffmpeg_exe(),
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_path),
        "-c:a",
        "libmp3lame",
        "-q:a",
        "4",
        output_mp3,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    list_path.unlink(missing_ok=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg concat audio failed: {result.stderr}")
