"""Mix: narration spine, music cues, sidechain ducking and two-pass loudness, with measurements."""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .. import music
from ..core.config import SAMPLE_RATE as SR
from ..core.context import Context
from ..core.storyboard import Duck, Storyboard
from ..timeline import Timeline
from . import ffmpeg

CROSSFADE_S, FIRST_FADE_S, LAST_FADE_S, CLICK_FADE_S = 2.0, 0.8, 3.0, 0.015
DUCK_SETTLE_S = 0.6  # skip the attack when measuring the steady ducking level
AAC_OVERSHOOT_DB = 0.5


@dataclass(frozen=True)
class MixReport:
    placeholder_cues: list[str]
    duck_under_speech_db: float | None
    duck_in_gaps_db: float | None
    voice_over_music_db: float | None

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def decode(path: Path) -> np.ndarray:
    command = ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    raw = subprocess.run(command, capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def encode(path: Path, samples: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    command = ["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-"]
    command += ["-c:a", "pcm_f32le", str(path)]
    subprocess.run(command, input=samples.astype("<f4").tobytes(), check=True)


def loudness(path: Path, af: str = "loudnorm=print_format=json") -> dict[str, float]:
    report = ffmpeg.run("-i", path, "-af", af, "-f", "null", "-")
    fields = json.loads(report[report.rindex("{") : report.rindex("}") + 1])
    return {k: float(v) for k, v in fields.items() if k != "normalization_type"}


def to_lufs(samples: np.ndarray, target: float, scratch: Path) -> np.ndarray:
    encode(scratch, samples)
    measured = loudness(scratch)["input_i"]
    scratch.unlink()
    return samples * 10 ** ((target - measured) / 20) if np.isfinite(measured) else samples


def fade(samples: np.ndarray, fade_in: float, fade_out: float) -> np.ndarray:
    samples = samples.copy()
    head, tail = min(int(fade_in * SR), samples.size), min(int(fade_out * SR), samples.size)
    samples[:head] *= np.linspace(0, 1, head, dtype=np.float32)
    samples[samples.size - tail :] *= np.linspace(1, 0, tail, dtype=np.float32)
    return samples


def loop_to(samples: np.ndarray, wanted: int) -> np.ndarray:
    """Repeat with crossfades until long enough, then cut to length."""
    overlap = min(int(CROSSFADE_S * SR), samples.size // 2)
    ramp = np.linspace(0, 1, overlap, dtype=np.float32)
    out = samples
    while out.size < wanted:
        join = out[out.size - overlap :] * (1 - ramp) + samples[:overlap] * ramp
        out = np.concatenate([out[: out.size - overlap], join, samples[overlap:]])
    return out[:wanted]


def place(track: np.ndarray, samples: np.ndarray, at_s: float) -> None:
    start = int(at_s * SR)
    size = min(samples.size, track.size - start)
    track[start : start + size] += samples[:size]


def voice_track(ctx: Context, sb: Storyboard, timeline: Timeline) -> np.ndarray:
    track = np.zeros(int(timeline.total * SR), np.float32)
    for shot in timeline.shots:
        if shot.speech_start is not None:
            line = decode(ctx.paths.narration(shot.id))
            line = to_lufs(line, sb["mix"]["narration_lufs"], ctx.paths.audio / "_scratch.wav")
            place(track, fade(line, CLICK_FADE_S, CLICK_FADE_S), shot.speech_start)
    return track


def music_track(ctx: Context, sb: Storyboard, timeline: Timeline) -> tuple[np.ndarray, list[str]]:
    track = np.zeros(int(timeline.total * SR), np.float32)
    placeholders: list[str] = []
    cues = sb["music"]["cues"]
    for index, cue in enumerate(cues):
        path, is_placeholder = music.chosen(ctx, sb, cue)
        if is_placeholder:
            placeholders.append(cue["id"])
        first, last = index == 0, index == len(cues) - 1
        start = timeline.cue_starts[cue["id"]] - (0 if first else CROSSFADE_S / 2)
        end = timeline.total if last else timeline.cue_starts[cues[index + 1]["id"]] + CROSSFADE_S / 2
        samples = to_lufs(decode(path), sb["mix"]["music_lufs"], ctx.paths.audio / "_scratch.wav")
        samples = loop_to(samples, int((end - start) * SR))
        samples = fade(samples, FIRST_FADE_S if first else CROSSFADE_S, LAST_FADE_S if last else CROSSFADE_S)
        place(track, samples, start)
    return track, placeholders


def duck(music_wav: Path, voice_wav: Path, out: Path, settings: Duck) -> None:
    compressor = (
        f"sidechaincompress=threshold={settings['threshold']}:ratio={settings['ratio']}"
        f":attack={settings['attack_ms']}:release={settings['release_ms']}"
    )
    graph = f"[0:a][1:a]{compressor}[o]"
    ffmpeg.run(
        "-i", music_wav, "-i", voice_wav, "-filter_complex", graph, "-map", "[o]", "-c:a", "pcm_f32le", out
    )


def normalise(source: Path, out: Path, target_lufs: float, true_peak_db: float) -> None:
    """Two-pass loudnorm, aimed slightly under the ceiling because AAC encoding overshoots."""
    tp = true_peak_db - AAC_OVERSHOOT_DB
    m = loudness(source, f"loudnorm=I={target_lufs}:TP={tp}:LRA=11:print_format=json")
    chain = (
        f"loudnorm=I={target_lufs}:TP={tp}:LRA=11"
        f":measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
        f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true"
    )
    ffmpeg.run("-i", source, "-af", chain, "-ar", SR, "-ac", 2, "-c:a", "pcm_s16le", out)
    after = loudness(out, f"loudnorm=I={target_lufs}:TP={tp}:LRA=11:print_format=json")
    if abs(after["input_i"] - target_lufs) > 0.3:
        gain = target_lufs - after["input_i"]
        limit = 10 ** (tp / 20)
        tmp = out.with_suffix(".tmp.wav")
        ffmpeg.run(
            "-i",
            out,
            "-af",
            f"volume={gain:.2f}dB,alimiter=limit={limit:.4f}:level=disabled",
            "-ar",
            SR,
            "-ac",
            2,
            "-c:a",
            "pcm_s16le",
            tmp,
        )
        tmp.replace(out)


def _rms_db(samples: np.ndarray) -> float:
    return float(20 * np.log10(np.sqrt(np.mean(samples**2)) + 1e-9))


def measure(
    timeline: Timeline, voice: np.ndarray, bed: np.ndarray, ducked: np.ndarray, placeholders: list[str]
) -> MixReport:
    size = min(voice.size, bed.size, ducked.size)
    voice, bed, ducked = voice[:size], bed[:size], ducked[:size]
    speech = np.zeros(size, bool)
    for shot in timeline.shots:
        if shot.speech_start is not None:
            begin = int((shot.speech_start + DUCK_SETTLE_S) * SR)
            speech[begin : int((shot.speech_start + shot.speech_s) * SR)] = True
    audible = np.abs(bed) > 1e-5
    under, gaps = speech & audible, ~speech & audible

    def change(a: np.ndarray, b: np.ndarray, mask: np.ndarray) -> float | None:
        return round(_rms_db(a[mask]) - _rms_db(b[mask]), 2) if mask.any() else None

    return MixReport(
        placeholders, change(ducked, bed, under), change(ducked, bed, gaps), change(voice, ducked, under)
    )


def build(ctx: Context, sb: Storyboard, timeline: Timeline) -> MixReport:
    """Write voice, music, ducked and mix WAVs, and report how far the score really drops."""
    folder, mix = ctx.paths.audio, sb["mix"]
    voice = voice_track(ctx, sb, timeline)
    bed, placeholders = music_track(ctx, sb, timeline)
    encode(folder / "voice.wav", voice)
    encode(folder / "music.wav", bed)
    duck(folder / "music.wav", folder / "voice.wav", folder / "ducked.wav", mix["duck"])
    ducked = decode(folder / "ducked.wav")
    size = min(ducked.size, voice.size)
    encode(folder / "premix.wav", ducked[:size] + voice[:size])
    normalise(folder / "premix.wav", folder / "mix.wav", mix["target_lufs"], mix["true_peak_db"])
    return measure(timeline, voice, bed, ducked, placeholders)
