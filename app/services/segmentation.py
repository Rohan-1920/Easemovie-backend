import re

from app.schemas import SceneDto, SegmentResponse


def split_story_to_scenes(text: str) -> SegmentResponse:
    raw = text.strip()
    segments = [s.strip() for s in re.split(r"(?<=[.!?])\s+", raw.replace("\n", " ")) if s.strip()]
    if not segments:
        segments = [raw]

    scenes = [
        SceneDto(index=i, text=segment, mood=_guess_mood(segment), camera=_camera_by_index(i))
        for i, segment in enumerate(segments, start=1)
    ]
    return SegmentResponse(scenes=scenes)


def _guess_mood(text: str) -> str:
    t = text.lower()
    if any(word in t for word in ("fight", "war", "danger", "storm", "escape")):
        return "intense"
    if any(word in t for word in ("love", "friend", "happy", "smile", "hope")):
        return "warm"
    if any(word in t for word in ("space", "future", "robot", "alien", "planet")):
        return "mysterious"
    return "neutral"


def _camera_by_index(index: int) -> str:
    cameras = ["wide shot", "close-up", "tracking shot", "overhead shot"]
    return cameras[(index - 1) % len(cameras)]
