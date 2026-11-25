"""Stage: moving shots. Wan 2.2 image-to-video where the storyboard asks for it; Ken Burns otherwise."""

from __future__ import annotations

from pathlib import Path

from .core import cache
from .core.config import ASPECTS
from .core.context import Context
from .core.gpu_batch import Job, run_jobs
from .core.log import log
from .core.storyboard import Shot, Storyboard

DEFAULT_NEGATIVE = (
    "text, watermark, subtitles, extra fingers, deformed hands, distorted face, morphing, flicker, "
    "fast motion, camera shake, low quality, oversaturated"
)
Clips = dict[tuple[str, str], Path | None]


def job(ctx: Context, sb: Storyboard, shot: Shot, aspect: str) -> Job:
    video, motion = sb["providers"]["video"], shot["motion"]
    portrait = (video["short_side"], video["long_side"])
    width, height = portrait if aspect == "vertical" else portrait[::-1]
    return {
        "name": f"{shot['id']}.{aspect}",
        "shot": shot["id"],
        "aspect": aspect,
        "image": f"{shot['id']}.{aspect}.png",
        "model": video["model"],
        "prompt": motion["prompt"],
        "negative_prompt": sb.get("negative_prompt") or DEFAULT_NEGATIVE,
        "seed": motion["seed"],
        "width": width,
        "height": height,
        "num_frames": video["num_frames"],
        "fps": video["fps"],
        "steps": video["steps"],
        "guidance": video["guidance"],
        "flow_shift": video["flow_shift"],
        "keyframe_sha": cache.file_digest(ctx.paths.keyframe(shot["id"], aspect)),
    }


def run(ctx: Context, sb: Storyboard) -> Clips:
    """Map (shot, aspect) to a clip, or to None where assembly should render Ken Burns."""
    jobs = {
        (shot["id"], aspect): job(ctx, sb, shot, aspect)
        for shot in sb["shots"]
        if shot["motion"]["backend"] == "wan"
        for aspect in ASPECTS
    }

    def target(j: Job) -> Path:
        return ctx.paths.clip(j["shot"], j["aspect"])

    def files(batch: list[Job]) -> dict[str, Path]:
        return {j["image"]: ctx.paths.keyframe(j["shot"], j["aspect"]) for j in batch}

    run_jobs(ctx, "shot", "wan", list(jobs.values()), files, target, ".mp4")
    clips: Clips = {(s["id"], a): None for s in sb["shots"] for a in ASPECTS}
    for key, j in jobs.items():
        if cache.is_fresh(target(j), j):
            clips[key] = target(j)
        else:
            log.info("shot %s: no clip, falling back to Ken Burns", j["name"])
    return clips
