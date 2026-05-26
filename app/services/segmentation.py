import re

from app.schemas import SceneDto, SegmentResponse
from app.services.story_analysis import guess_mood, pick_voice_for_text


def _elevenlabs_ready() -> bool:
    from app.services.voice_generation import elevenlabs_configured

    return elevenlabs_configured()


def split_story_to_scenes(text: str) -> SegmentResponse:
    raw = text.strip()
    segments = [s.strip() for s in re.split(r"(?<=[.!?])\s+", raw.replace("\n", " ")) if s.strip()]
    if not segments:
        segments = [raw]

    use_eleven = _elevenlabs_ready()
    scenes = []
    for i, segment in enumerate(segments, start=1):
        mood = guess_mood(segment)
        voice_choice = pick_voice_for_text(
            segment,
            voice="auto",
            story_context=raw,
            use_elevenlabs=use_eleven,
        )
        scenes.append(
            SceneDto(
                index=i,
                text=segment,
                mood=mood,
                camera=_camera_by_index(i),
                voice=voice_choice.voice_id,
                voice_name=voice_choice.voice_name,
            )
        )
    return SegmentResponse(scenes=scenes)


def _camera_by_index(index: int) -> str:
    cameras = ["wide shot", "close-up", "tracking shot", "overhead shot"]
    return cameras[(index - 1) % len(cameras)]
