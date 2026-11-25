"""Timing. Measured narration sets shot length; cuts snap to the cue's nominal beat and to whole frames."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

from .core.config import FPS
from .core.context import Context
from .core.errors import TimingError
from .core.storyboard import Storyboard
from .media.ffmpeg import duration

SUBTITLE_WIDTH, SUBTITLE_LINES = 40, 2


@dataclass(frozen=True)
class TimedShot:
    id: str
    start: float
    end: float
    speech_start: float | None
    speech_s: float

    @property
    def length(self) -> float:
        return self.end - self.start


@dataclass(frozen=True)
class Subtitle:
    shot: str
    start: float
    end: float
    lines: list[str]

    @property
    def chars_per_second(self) -> float:
        return len(" ".join(self.lines)) / (self.end - self.start)


@dataclass(frozen=True)
class Timeline:
    shots: list[TimedShot]
    subtitles: list[Subtitle]
    cue_starts: dict[str, float]
    picture_end: float
    total: float

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def wrap(text: str, width: int = SUBTITLE_WIDTH) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    return [*lines, current] if current else lines


def subtitles(shot_id: str, text: str, start: float, length: float) -> list[Subtitle]:
    """Split into events of at most two lines, sharing the time by character count."""
    lines = wrap(text)
    chunks = [lines[i : i + SUBTITLE_LINES] for i in range(0, len(lines), SUBTITLE_LINES)]
    total = sum(len(" ".join(chunk)) for chunk in chunks) or 1
    events, time_s = [], start
    for chunk in chunks:
        share = length * len(" ".join(chunk)) / total
        events.append(Subtitle(shot_id, round(time_s, 3), round(time_s + share, 3), chunk))
        time_s += share
    return events


def _snap(end: float, anchor: float, beat: float | None) -> float:
    if beat:
        end = anchor + math.ceil((end - anchor) / beat - 1e-6) * beat
    return round(end * FPS) / FPS


def build(ctx: Context, sb: Storyboard, *, strict: bool = True) -> Timeline:
    mix = sb["mix"]
    cues = {cue["start_shot"]: cue for cue in sb["music"]["cues"]}
    time_s, anchor, beat = 0.0, 0.0, None
    shots: list[TimedShot] = []
    subs: list[Subtitle] = []
    cue_starts: dict[str, float] = {}
    for shot in sb["shots"]:
        cue = cues.get(shot["id"])
        if cue:
            cue_starts[cue["id"]] = anchor = time_s
            beat = 60 / cue["bpm"] if mix.get("snap_to_beat") else None
        spoken = bool(shot["narration"]["text"].strip())
        speech = duration(ctx.paths.narration(shot["id"])) if spoken else 0.0
        padded = speech + mix["head_pad_s"] + mix["tail_pad_s"] if spoken else 0.0
        end = _snap(time_s + max(shot["min_duration_s"], padded), anchor, beat)
        voice_at = time_s + mix["head_pad_s"]
        shots.append(TimedShot(shot["id"], time_s, end, voice_at if spoken else None, speech))
        if spoken:
            read_time = speech + min(0.3, mix["tail_pad_s"])
            subs += subtitles(shot["id"], shot["narration"]["subtitle_en"], voice_at, read_time)
        time_s = end
    total = round((time_s + sb["end_card"]["duration_s"]) * FPS) / FPS
    low, high = sb["duration_s"]["min"], sb["duration_s"]["max"]
    if strict and not low <= total <= high:
        raise TimingError(
            f"the film would be {total:.2f}s; the storyboard allows {low}-{high}s. "
            "Edit the narration or min_duration_s."
        )
    return Timeline(shots, subs, cue_starts, time_s, total)
