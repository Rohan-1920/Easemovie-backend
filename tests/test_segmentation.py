"""Segmentation unit tests (no HTTP)."""

from __future__ import annotations

from app.services.segmentation import split_story_to_scenes


def test_single_sentence():
    result = split_story_to_scenes("Hello world.")
    assert len(result.scenes) >= 1


def test_two_sentences():
    result = split_story_to_scenes("Scene one here. Scene two there.")
    assert len(result.scenes) >= 2
