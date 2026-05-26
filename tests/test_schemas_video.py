from __future__ import annotations

import pytest

from app.schemas import VideoFromImageRequest


def test_video_from_image_requires_url():
    with pytest.raises(ValueError):
        VideoFromImageRequest(
            text="A forest scene",
            style="Anime",
            emotion="warm",
        )


def test_video_from_image_accepts_image_urls():
    payload = VideoFromImageRequest(
        text="Scene",
        style="Anime",
        emotion="warm",
        image_urls=["http://example.com/a.png", "http://example.com/b.png"],
    )
    assert payload.image_urls is not None
    assert len(payload.image_urls) == 2
