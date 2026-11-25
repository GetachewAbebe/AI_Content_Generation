"""Automatic checks on the finished films, written to outputs/final/qc.json."""

from __future__ import annotations

import json
from typing import Any

from .core import cache
from .core.config import ASPECTS, FPS
from .core.context import Context
from .core.log import log
from .core.storyboard import Storyboard
from .media import audio, ffmpeg
from .timeline import SUBTITLE_LINES, SUBTITLE_WIDTH, Timeline

MIN_S, MAX_S, FRAME_SLACK_S = 60, 90, 0.05
LOUDNESS_TOLERANCE_LU, MAX_CHARS_PER_SECOND, MIN_DUCK_DB = 1.0, 20.0, -3.0

Check = dict[str, Any]


def _check(name: str, ok: bool, detail: Any) -> Check:
    return {"check": name, "ok": bool(ok), "detail": detail}


def _file_checks(ctx: Context, sb: Storyboard, aspect: str) -> tuple[list[Check], dict[str, Any]]:
    path = ctx.paths.film(aspect)
    info = ffmpeg.probe(path)
    streams = {s["codec_type"]: s for s in info["streams"]}
    video, sound = streams["video"], streams["audio"]
    seconds = float(info["format"]["duration"])
    level = audio.loudness(path)
    size = (video["width"], video["height"])
    target, ceiling = sb["mix"]["target_lufs"], sb["mix"]["true_peak_db"]
    formats = [video["codec_name"], sound["codec_name"], video["r_frame_rate"]]
    checks = [
        _check(f"{aspect}: duration 60-90 s", MIN_S <= seconds <= MAX_S + FRAME_SLACK_S, round(seconds, 2)),
        _check(f"{aspect}: size", size == ASPECTS[aspect], size),
        _check(f"{aspect}: H.264, AAC, {FPS} fps", formats == ["h264", "aac", f"{FPS}/1"], formats),
        _check(
            f"{aspect}: loudness near {target} LUFS",
            abs(level["input_i"] - target) <= LOUDNESS_TOLERANCE_LU,
            level["input_i"],
        ),
        _check(
            f"{aspect}: true peak under {ceiling} dB", level["input_tp"] <= ceiling + 0.1, level["input_tp"]
        ),
    ]
    facts = {
        "duration_s": round(seconds, 3),
        "size": size,
        "lufs": level["input_i"],
        "true_peak_db": level["input_tp"],
        "bytes": path.stat().st_size,
        "sha256": cache.file_digest(path),
    }
    return checks, facts


def _content_checks(timeline: Timeline, mix: audio.MixReport) -> list[Check]:
    subs = timeline.subtitles
    short = all(len(e.lines) <= SUBTITLE_LINES and max(map(len, e.lines)) <= SUBTITLE_WIDTH for e in subs)
    fastest = round(max((e.chars_per_second for e in subs), default=0), 1)
    drop = mix.duck_under_speech_db
    return [
        _check("subtitles: at most 2 lines of 40 characters", short, len(subs)),
        _check("subtitles: at most 20 characters per second", fastest <= MAX_CHARS_PER_SECOND, fastest),
        _check("score ducked at least 3 dB under speech", drop is not None and drop <= MIN_DUCK_DB, drop),
        _check("original score in place", not mix.placeholder_cues, mix.placeholder_cues),
    ]


def run(
    ctx: Context, sb: Storyboard, timeline: Timeline, mix: audio.MixReport, sources: dict[str, str]
) -> dict[str, Any]:
    checks: list[Check] = []
    files: dict[str, Any] = {}
    for aspect in ASPECTS:
        found, files[aspect] = _file_checks(ctx, sb, aspect)
        checks += found
    checks += _content_checks(timeline, mix)
    report = {"checks": checks, "mix": mix.to_json(), "shot_sources": sources, "files": files}
    (ctx.paths.final / "qc.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    for item in checks:
        log.info("  %s %s: %s", "ok  " if item["ok"] else "FAIL", item["check"], item["detail"])
    return report
