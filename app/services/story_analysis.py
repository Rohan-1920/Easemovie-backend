"""Story mood/genre detection and ElevenLabs voice selection."""

from __future__ import annotations

from dataclasses import dataclass

# ElevenLabs premade voices (free tier).
VOICE_ALIASES: dict[str, str] = {
    "adam": "pNInz6obpgDQGcFmaJgB",
    "rachel": "21m00Tcm4TlvDq8ikWAM",
    "alice": "Xb7hH8MSUJpSbSDYk0k2",
    "charlotte": "XB0fDUnXU5powFXDhCwa",
    "daniel": "onwK4e9ZLuTAKqWW03F9",
    "domi": "AZnzlk1XvdvUeBnXmlld",
    "antoni": "ErXwobaYiN019PkySvjV",
    "bill": "pqHfZKP75CvOlQylNhV4",
    "lily": "pFZP5JQG7iQjIQuC4Bku",
}

VOICE_NAMES: dict[str, str] = {voice_id: name.title() for name, voice_id in VOICE_ALIASES.items()}

STORY_GENRE_VOICES: dict[str, str] = {
    "fairy_tale": VOICE_ALIASES["alice"],
    "warm": VOICE_ALIASES["rachel"],
    "mysterious": VOICE_ALIASES["daniel"],
    "intense": VOICE_ALIASES["domi"],
    "neutral": VOICE_ALIASES["adam"],
}

MOOD_VOICES: dict[str, str] = {
    "fairy": VOICE_ALIASES["alice"],
    "warm": VOICE_ALIASES["rachel"],
    "mysterious": VOICE_ALIASES["daniel"],
    "intense": VOICE_ALIASES["domi"],
    "neutral": VOICE_ALIASES["adam"],
}

# Edge TTS fallback when ElevenLabs key is missing.
EDGE_MOOD_VOICES: dict[str, str] = {
    "fairy": "en-GB-SoniaNeural",
    "warm": "en-US-JennyNeural",
    "mysterious": "en-GB-RyanNeural",
    "intense": "en-US-GuyNeural",
    "neutral": "en-US-AriaNeural",
}


@dataclass(frozen=True)
class VoiceChoice:
    voice_id: str
    voice_name: str
    mood: str
    story_genre: str
    provider: str  # elevenlabs | edge


def guess_mood(text: str) -> str:
    t = text.lower()
    if any(
        word in t
        for word in (
            "fairy",
            "once upon",
            "princess",
            "enchanted",
            "magical",
            "lullaby",
            "happily ever after",
        )
    ):
        return "fairy"
    if any(word in t for word in ("fight", "war", "danger", "storm", "escape", "battle", "chase")):
        return "intense"
    if any(word in t for word in ("love", "friend", "happy", "smile", "hope", "joy", "kind")):
        return "warm"
    if any(word in t for word in ("space", "future", "robot", "alien", "planet", "galaxy", "mystery")):
        return "mysterious"
    return "neutral"


def classify_story_genre(text: str) -> str:
    t = text.lower()
    if any(
        word in t
        for word in (
            "once upon",
            "fairy",
            "princess",
            "dragon",
            "enchanted",
            "happily ever after",
            "magical forest",
            "little bird",
        )
    ):
        return "fairy_tale"
    if any(word in t for word in ("space", "future", "robot", "alien", "planet", "galaxy")):
        return "mysterious"
    if any(word in t for word in ("fight", "war", "battle", "danger", "escape", "chase", "storm")):
        return "intense"
    if any(word in t for word in ("love", "friend", "happy", "joy", "hope", "smile", "kind")):
        return "warm"
    return "neutral"


def resolve_explicit_voice(voice: str, *, use_elevenlabs: bool) -> VoiceChoice | None:
    cleaned = voice.strip()
    if not cleaned or cleaned.lower() == "auto":
        return None

    if cleaned.lower() in VOICE_ALIASES:
        voice_id = VOICE_ALIASES[cleaned.lower()]
        return VoiceChoice(
            voice_id=voice_id,
            voice_name=VOICE_NAMES[voice_id],
            mood="neutral",
            story_genre="neutral",
            provider="elevenlabs",
        )

    if cleaned in VOICE_NAMES:
        return VoiceChoice(
            voice_id=cleaned,
            voice_name=VOICE_NAMES[cleaned],
            mood="neutral",
            story_genre="neutral",
            provider="elevenlabs",
        )

    if cleaned.startswith("en-"):
        return VoiceChoice(
            voice_id=cleaned,
            voice_name=cleaned,
            mood="neutral",
            story_genre="neutral",
            provider="edge",
        )

    if use_elevenlabs:
        return VoiceChoice(
            voice_id=cleaned,
            voice_name=cleaned[:12],
            mood="neutral",
            story_genre="neutral",
            provider="elevenlabs",
        )

    return None


def pick_voice_for_text(
    text: str,
    *,
    voice: str = "auto",
    story_context: str | None = None,
    use_elevenlabs: bool = True,
    mood_override: str | None = None,
) -> VoiceChoice:
    explicit = resolve_explicit_voice(voice, use_elevenlabs=use_elevenlabs)
    if explicit:
        return explicit

    mood = (mood_override or "").strip().lower() or guess_mood(text)
    genre = classify_story_genre(story_context or text)

    if use_elevenlabs:
        if genre == "fairy_tale" and mood in ("neutral", "warm", "fairy"):
            voice_id = STORY_GENRE_VOICES["fairy_tale"]
        elif mood in MOOD_VOICES:
            voice_id = MOOD_VOICES[mood]
        else:
            voice_id = STORY_GENRE_VOICES.get(genre, STORY_GENRE_VOICES["neutral"])
        return VoiceChoice(
            voice_id=voice_id,
            voice_name=VOICE_NAMES[voice_id],
            mood=mood,
            story_genre=genre,
            provider="elevenlabs",
        )

    edge_voice = EDGE_MOOD_VOICES.get(mood, EDGE_MOOD_VOICES["neutral"])
    if genre == "fairy_tale":
        edge_voice = EDGE_MOOD_VOICES["fairy"]
    return VoiceChoice(
        voice_id=edge_voice,
        voice_name=edge_voice,
        mood=mood,
        story_genre=genre,
        provider="edge",
    )
