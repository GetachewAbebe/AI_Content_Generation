"""Stage: narration. One WAV per shot, so one changed line costs exactly one TTS call."""

from __future__ import annotations

from typing import Any

from .core import cache
from .core.context import Context
from .core.log import log
from .core.runlog import CallInfo, ModelResult
from .core.storyboard import Shot, Storyboard


def inputs(sb: Storyboard, shot: Shot) -> dict[str, Any]:
    tts, line = sb["providers"]["tts"], shot["narration"]
    return {
        "stage": "narration",
        "model": tts["model"],
        "voice": tts["voice"],
        "style": line.get("style") or tts["style"],
        "text": line["text"],
        "take": line.get("take", 1),  # the API documents no seed: bump this to ask for another performance
    }


def generate(ctx: Context, shot: Shot, wanted: dict[str, Any]) -> None:
    params = {key: wanted[key] for key in ("voice", "style", "take")} | {"chars": len(wanted["text"])}
    speech = ctx.providers.speech
    info = CallInfo(
        "narration", shot["id"], speech.name, wanted["model"], params, input_hash=cache.digest(wanted)
    )

    def speak() -> ModelResult:
        return speech.synthesise(
            model=wanted["model"], voice=wanted["voice"], style=wanted["style"], text=wanted["text"]
        )

    result = ctx.runlog.call(info, speak)
    cache.store(ctx.paths.narration(shot["id"]), result.data, wanted, run_id=ctx.runlog.run_id)


def run(ctx: Context, sb: Storyboard) -> int:
    """Generate missing or stale lines. Returns the number of lines generated."""
    calls = 0
    for shot in sb["shots"]:
        wanted = inputs(sb, shot)
        if wanted["text"].strip() and not cache.is_fresh(ctx.paths.narration(shot["id"]), wanted):
            log.info("narration %s: generating", shot["id"])
            generate(ctx, shot, wanted)
            calls += 1
    return calls
