from __future__ import annotations

from app.providers.video_model import _scene_emotion, _scene_motion_text, video_source_label


def test_scene_motion_text_uses_scene_line():
    text = _scene_motion_text(
        0,
        scene_texts=["Mira walks through the glowing forest."],
        fallback_prompt="Composed short film from scenes",
    )
    assert "Mira" in text


def test_scene_motion_text_fallback_for_index():
    text = _scene_motion_text(
        2,
        scene_texts=["Scene one only"],
        fallback_prompt="Composed short film from scenes",
    )
    assert "scene 3" in text.lower()


def test_scene_emotion_default():
    assert _scene_emotion(0, None) == "neutral"


def test_video_source_label_multi_svd():
    assert video_source_label("sunfjun/stable-video-diffusion", multi_scene=True) == "svd_multi"
