"""Stage: assembly. A deterministic FFmpeg edit of both aspect ratios from cached media."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import qc, timeline
from .core import cache
from .core.config import ASPECTS, FONTS, FPS
from .core.context import Context
from .core.log import log
from .core.storyboard import Storyboard
from .media import audio, ffmpeg, picture, subtitles
from .shots import Clips

FADE_S = 0.5


def _concat_list(ctx: Context, aspect: str, segments: list[Path]) -> Path:
    path = ctx.paths.out / "segments" / f"{aspect}.txt"
    path.write_text("".join(f"file '{p.resolve()}'\n" for p in segments))
    return path


def render(
    ctx: Context, sb: Storyboard, tl: timeline.Timeline, clips: Clips, aspect: str, subs: Path
) -> Path:
    segments = [
        picture.segment(ctx, shot, aspect, clips.get((shot["id"], aspect)), timed.length)
        for shot, timed in zip(sb["shots"], tl.shots, strict=True)
    ]
    segments.append(picture.end_card(ctx, sb, aspect))
    listing = _concat_list(ctx, aspect, segments)
    end = tl.picture_end
    look = (
        f"fade=in:st=0:d={FADE_S},fade=out:st={end - FADE_S}:d={FADE_S}:enable='lt(t,{end})',"
        f"ass='{subs}':fontsdir='{FONTS}'"
    )
    labels = ["-metadata", f"title={sb['title']['en']}"]
    labels += ["-metadata", "comment=Made with AI. " + " | ".join(sb["end_card"]["lines"])]
    log.info("rendering %s", aspect)
    target = ctx.paths.film(aspect)
    with cache.atomic(target) as temp:
        ffmpeg.run(
            *("-f", "concat", "-safe", 0, "-i", listing, "-i", ctx.paths.audio / "mix.wav", "-vf", look),
            *picture.encoder(19),
            *("-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", *labels, "-t", tl.total, temp),
        )
    listing.unlink()  # it holds absolute paths
    return target


def run(ctx: Context, sb: Storyboard, clips: Clips) -> dict[str, Any]:
    tl = timeline.build(ctx, sb)
    ctx.paths.final.mkdir(parents=True, exist_ok=True)
    plan = json.dumps(tl.to_json(), indent=1, ensure_ascii=False)
    (ctx.paths.final / "timeline.json").write_text(plan + "\n")
    subs = subtitles.write(ctx, sb, tl)
    log.info("mixing audio")
    mix = audio.build(ctx, sb, tl)
    for aspect in ASPECTS:
        render(ctx, sb, tl, clips, aspect, subs[aspect])
    sources = {f"{shot}.{aspect}": "wan" if clip else "kenburns" for (shot, aspect), clip in clips.items()}
    return qc.run(ctx, sb, tl, mix, sources)


def radio(ctx: Context, sb: Storyboard) -> Path:
    """Narration over music on black, without subtitles, so listeners judge the story by ear."""
    tl = timeline.build(ctx, sb, strict=False)
    mix = audio.build(ctx, sb, tl)
    target = ctx.paths.final / "radio_cut.mp4"
    with cache.atomic(target) as temp:
        ffmpeg.run(
            *("-f", "lavfi", "-i", f"color=black:s=720x1280:r={FPS}", "-i", ctx.paths.audio / "mix.wav"),
            *picture.encoder(28),
            *("-c:a", "aac", "-b:a", "160k", "-t", tl.total, "-movflags", "+faststart", temp),
        )
    log.info("radio cut: %s (%.1fs) %s", target, tl.total, mix)
    for shot in tl.shots:
        log.info("  %-14s %6.2f -> %6.2f  speech %.2fs", shot.id, shot.start, shot.end, shot.speech_s)
    return target
