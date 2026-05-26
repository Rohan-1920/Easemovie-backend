from __future__ import annotations

from app.services.story_analysis import (
    classify_story_genre,
    guess_mood,
    pick_voice_for_text,
)


def test_guess_mood_fairy_tale():
    assert guess_mood("Once upon a time, a little fairy lived in the forest.") == "fairy"


def test_guess_mood_intense():
    assert guess_mood("They had to escape the storm and fight for survival.") == "intense"


def test_classify_story_genre_fairy():
    text = "Once upon a time, a princess lived happily ever after in a magical forest."
    assert classify_story_genre(text) == "fairy_tale"


def test_pick_voice_auto_fairy_tale_uses_alice():
    text = "Once upon a time, Lila the fairy helped a little bird."
    choice = pick_voice_for_text(text, voice="auto", use_elevenlabs=True)
    assert choice.voice_name == "Alice"
    assert choice.story_genre == "fairy_tale"
    assert choice.provider == "elevenlabs"


def test_pick_voice_auto_intense_uses_domi():
    text = "The soldiers fought in a dangerous battle during the storm."
    choice = pick_voice_for_text(text, voice="auto", use_elevenlabs=True)
    assert choice.voice_name == "Domi"
    assert choice.mood == "intense"


def test_pick_voice_explicit_adam():
    choice = pick_voice_for_text("Hello world.", voice="Adam", use_elevenlabs=True)
    assert choice.voice_name == "Adam"


def test_pick_voice_edge_fallback_when_no_elevenlabs():
    text = "Once upon a time, a fairy smiled with joy."
    choice = pick_voice_for_text(text, voice="auto", use_elevenlabs=False)
    assert choice.provider == "edge"
    assert choice.voice_id.startswith("en-")


def test_segment_includes_voice_fields(client):
    response = client.post(
        "/segment",
        json={"text": "Once upon a time, a fairy named Lila smiled. She helped a lost bird."},
    )
    assert response.status_code == 200
    scenes = response.json()["scenes"]
    assert scenes[0]["voice"]
    assert scenes[0]["voice_name"]
