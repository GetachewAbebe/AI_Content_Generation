"""Command line: heritage {film,radio,validate,script,narration,keyframes,shots,music,smoke,...}."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable
from pathlib import Path

from . import assemble, keyframes, music, narration, script, shots, validate
from .core.config import ROOT, Paths, load_env, redact
from .core.context import Context
from .core.errors import PipelineError
from .core.log import log, setup_logging
from .core.runlog import RunLog
from .core.storyboard import Storyboard
from .providers.base import Providers
from .tools import consistency, costs, duck_sweep, showcase, smoke, tts_bench

QC_FAILED = 2


def make_context(*, mock: bool, allow_gpu: bool) -> Context:
    if mock:
        from .providers.fake import fake_providers  # noqa: PLC0415 - test-only dependency

        paths = Paths(ROOT / "build" / "mock")
        return Context(paths, RunLog(paths.runs), fake_providers(paths.base), allow_gpu)
    from .providers.cloudflare import Cloudflare  # noqa: PLC0415
    from .providers.gemini import Gemini  # noqa: PLC0415
    from .providers.kaggle import Kaggle  # noqa: PLC0415

    load_env()
    paths = Paths(ROOT)
    gemini = Gemini()
    return Context(
        paths, RunLog(paths.runs), Providers(gemini, Cloudflare(), gemini, Kaggle(paths.remote)), allow_gpu
    )


def film(ctx: Context, sb: Storyboard) -> int:
    log.info("narration: %d model call(s)", narration.run(ctx, sb))
    log.info("keyframes: %d model call(s)", keyframes.run(ctx, sb))
    music.run(ctx, sb)
    report = assemble.run(ctx, sb, shots.run(ctx, sb))
    failing = [c["check"] for c in report["checks"] if not c["ok"]]
    log.info("films are in %s; failing checks: %s", ctx.paths.final, failing or "none")
    return QC_FAILED if failing else 0


def radio(ctx: Context, sb: Storyboard) -> int:
    log.info("narration: %d model call(s)", narration.run(ctx, sb))
    assemble.radio(ctx, sb)
    return 0


def _done(func: Callable[[Context, Storyboard], object]) -> Callable[[Context, Storyboard], int]:
    def command(ctx: Context, sb: Storyboard) -> int:
        func(ctx, sb)
        return 0

    return command


def _images_then_shots(ctx: Context, sb: Storyboard) -> None:
    keyframes.run(ctx, sb)
    shots.run(ctx, sb)


STORYBOARD_COMMANDS: dict[str, Callable[[Context, Storyboard], int]] = {
    "film": film,
    "radio": radio,
    "validate": _done(lambda _ctx, _sb: None),
    "narration": _done(narration.run),
    "keyframes": _done(keyframes.run),
    "shots": _done(_images_then_shots),
    "music": _done(music.run),
    "consistency": _done(consistency.run),
    "duck-sweep": _done(duck_sweep.run),
    "showcase": _done(showcase.run),
}
PLAIN_COMMANDS: dict[str, Callable[[Context], object]] = {
    "script": script.run,
    "smoke": smoke.run,
    "costs": costs.run,
    "tts-bench": tts_bench.run,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="heritage", description=__doc__)
    parser.add_argument("command", choices=[*STORYBOARD_COMMANDS, *PLAIN_COMMANDS])
    parser.add_argument("--storyboard", type=Path, default=ROOT / "storyboard.json")
    parser.add_argument("--no-gpu", action="store_true", help="never submit GPU jobs")
    parser.add_argument("--mock", action="store_true", help="fake providers; writes only to build/mock")
    args = parser.parse_args(argv)
    setup_logging()
    mock = args.mock or os.environ.get("HERITAGE_MODE") == "mock"
    ctx = make_context(mock=mock, allow_gpu=not args.no_gpu)
    try:
        if args.command in PLAIN_COMMANDS:
            PLAIN_COMMANDS[args.command](ctx)
            return 0
        sb = validate.load(args.storyboard)
        log.info(
            "storyboard valid: %d shots, %s%s",
            len(sb["shots"]),
            sb["language"]["name"],
            " [MOCK]" if mock else "",
        )
        return STORYBOARD_COMMANDS[args.command](ctx, sb)
    except PipelineError as err:
        log.info("stopped: %s", redact(str(err)))
        log.info("everything finished so far is cached; rerun to continue")
        return 1


if __name__ == "__main__":
    sys.exit(main())
