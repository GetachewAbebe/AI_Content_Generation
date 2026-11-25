"""Stage: music. ACE-Step candidates per cue; a local synth is the clearly marked placeholder."""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

from .core import cache
from .core.config import SAMPLE_RATE
from .core.context import Context
from .core.gpu_batch import Job, run_jobs
from .core.storyboard import Cue, Storyboard

PENTATONIC = (0, 2, 4, 7, 9, 12, 14, 16)
ROOT_HZ = 146.83


def job(sb: Storyboard, cue: Cue, seed: int) -> Job:
    config = sb["providers"]["music"]
    return {
        "name": f"{cue['id']}.{seed}",
        "cue": cue["id"],
        "model": config["model"],
        "steps": config["steps"],
        "caption": cue["caption"],
        "bpm": cue["bpm"],
        "keyscale": cue["keyscale"],
        "duration_s": cue["duration_s"],
        "seed": seed,
    }


def run(ctx: Context, sb: Storyboard) -> None:
    jobs = [job(sb, cue, seed) for cue in sb["music"]["cues"] for seed in cue["seeds"]]
    run_jobs(ctx, "music", "ace", jobs, lambda _: {}, lambda j: ctx.paths.score(j["cue"], j["seed"]), ".wav")


def chosen(ctx: Context, sb: Storyboard, cue: Cue) -> tuple[Path, bool]:
    """The chosen candidate and False, or the placeholder and True."""
    path = ctx.paths.score(cue["id"], cue["chosen_seed"])
    if cache.is_fresh(path, job(sb, cue, cue["chosen_seed"])):
        return path, False
    path = ctx.paths.score(cue["id"], "placeholder")
    wanted = {
        "placeholder": True,
        "bpm": cue["bpm"],
        "duration_s": cue["duration_s"],
        "seed": cue["chosen_seed"],
    }
    if not cache.is_fresh(path, wanted):
        with cache.atomic(path) as temp:
            _write_wav(temp, pluck_sketch(cue))
        cache.record(path, wanted, provider="local-synth")
    return path, True


def _pluck(rng: np.random.Generator, frequency: float, length: int) -> np.ndarray:
    """One Karplus-Strong string, computed a period at a time."""
    period = int(SAMPLE_RATE / frequency)
    buffer = rng.uniform(-1, 1, period).astype(np.float32)
    tone = np.empty(length, np.float32)
    for start in range(0, length, period):
        size = min(period, length - start)
        tone[start : start + size] = buffer[:size]
        buffer = 0.498 * (buffer + np.roll(buffer, 1))
    return tone


def pluck_sketch(cue: Cue) -> np.ndarray:
    """A deterministic pentatonic sketch. No model is involved, so it is never the film's score."""
    rng = np.random.default_rng(cue["chosen_seed"])
    total, length = int(cue["duration_s"] * SAMPLE_RATE), int(2.2 * SAMPLE_RATE)
    out = np.zeros(total + length, np.float32)
    beat, time_s, degree = 60 / cue["bpm"], 0.0, 4
    while time_s < cue["duration_s"]:
        degree = int(np.clip(degree + rng.integers(-2, 3), 0, len(PENTATONIC) - 1))
        at = int(time_s * SAMPLE_RATE)
        out[at : at + length] += 0.25 * _pluck(rng, ROOT_HZ * 2 ** (PENTATONIC[degree] / 12), length)
        time_s += beat * float(rng.choice([1, 1, 2]))
    return out[:total]


def _write_wav(path: Path, samples: np.ndarray) -> None:
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(SAMPLE_RATE)
        out.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())
