"""Static types for the storyboard. The JSON Schema is the runtime check; these help editors and mypy."""

from __future__ import annotations

from typing import NotRequired, TypedDict


class Bilingual(TypedDict):
    native: str
    en: str


class Language(TypedDict):
    code: str
    name: str


class Range(TypedDict):
    min: float
    max: float


class Character(TypedDict):
    id: str
    description: str
    real_person: bool
    consent_id: NotRequired[str]


class Reference(TypedDict):
    id: str
    kind: str
    prompt: str
    seed: int
    characters: NotRequired[list[str]]
    references: NotRequired[list[str]]


class TtsConfig(TypedDict):
    model: str
    voice: str
    style: str


class ImageConfig(TypedDict):
    model: str
    steps: int


class VideoConfig(TypedDict):
    model: str
    long_side: int
    short_side: int
    num_frames: int
    fps: int
    steps: int
    guidance: float
    flow_shift: float


class MusicConfig(TypedDict):
    model: str
    steps: int


class ProviderConfig(TypedDict):
    tts: TtsConfig
    image: ImageConfig
    video: VideoConfig
    music: MusicConfig


class Keyframe(TypedDict):
    prompt: str
    seed: int
    references: list[str]
    characters: list[str]


class Motion(TypedDict):
    backend: str
    prompt: str
    seed: int
    kenburns: str
    why_backend: NotRequired[str]


class Narration(TypedDict):
    text: str
    subtitle_en: str
    style: NotRequired[str]
    take: NotRequired[int]


class Shot(TypedDict):
    id: str
    reason: str
    shot_size: str
    min_duration_s: float
    keyframe: Keyframe
    motion: Motion
    narration: Narration


class Cue(TypedDict):
    id: str
    start_shot: str
    purpose: str
    caption: str
    bpm: int
    keyscale: str
    duration_s: float
    seeds: list[int]
    chosen_seed: int
    why_chosen: NotRequired[str]


class Music(TypedDict):
    cues: list[Cue]


class Duck(TypedDict):
    threshold: float
    ratio: float
    attack_ms: float
    release_ms: float


class Mix(TypedDict):
    target_lufs: float
    true_peak_db: float
    narration_lufs: float
    music_lufs: float
    duck: Duck
    head_pad_s: float
    tail_pad_s: float
    snap_to_beat: NotRequired[bool]


class EndCard(TypedDict):
    duration_s: float
    lines: list[str]


class Storyboard(TypedDict):
    version: int
    title: Bilingual
    language: Language
    logline: str
    audience: str
    intent: str
    duration_s: Range
    style_block: str
    negative_prompt: NotRequired[str]
    characters: list[Character]
    references: list[Reference]
    providers: ProviderConfig
    shots: list[Shot]
    music: Music
    mix: Mix
    end_card: EndCard
