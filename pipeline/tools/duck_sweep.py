"""Measure ducking settings on the film's real narration and score. No model calls."""

from __future__ import annotations

import json

from .. import timeline
from ..core.context import Context
from ..core.log import log
from ..core.storyboard import Duck, Storyboard
from ..media import audio

SETTINGS: list[Duck] = [
    {"threshold": 0.02, "ratio": 6, "attack_ms": 300, "release_ms": 1500},  # the brief's suggestion
    {"threshold": 0.05, "ratio": 6, "attack_ms": 300, "release_ms": 1500},
    {"threshold": 0.05, "ratio": 3, "attack_ms": 300, "release_ms": 1500},
    {"threshold": 0.02, "ratio": 3, "attack_ms": 300, "release_ms": 1500},
    {"threshold": 0.05, "ratio": 3, "attack_ms": 150, "release_ms": 800},
]


def run(ctx: Context, sb: Storyboard) -> None:
    tl = timeline.build(ctx, sb, strict=False)
    audio.build(ctx, sb, tl)
    folder = ctx.paths.audio
    voice, bed = audio.decode(folder / "voice.wav"), audio.decode(folder / "music.wav")
    results = []
    for settings in SETTINGS:
        scratch = folder / "_sweep.wav"
        audio.duck(folder / "music.wav", folder / "voice.wav", scratch, settings)
        report = audio.measure(tl, voice, bed, audio.decode(scratch), []).to_json()
        scratch.unlink()
        report.pop("placeholder_cues")
        results.append({**settings, **report})
        log.info("%s -> %s", settings, report)
    out = ctx.paths.out / "eval" / "duck_sweep.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=1) + "\n")
