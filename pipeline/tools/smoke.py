"""One small real call per provider. Every result, including failures, goes to runs.jsonl."""

from __future__ import annotations

import io
from collections.abc import Callable

from PIL import Image

from ..core.context import Context
from ..core.errors import PipelineError
from ..core.log import log
from ..core.runlog import CallInfo, ModelResult

TEXT, SPEECH, KLEIN = "gemini-3.8-flash", "gemini-3.8-flash-tts", "@cf/black-forest-labs/flux-2-klein-4b"
PROBE_SIZE = (720, 1280)


def _try(ctx: Context, info: CallInfo, func: Callable[[], ModelResult]) -> ModelResult | None:
    try:
        result = ctx.runlog.call(info, func, attempts=2)
    except PipelineError as err:
        log.info("FAIL  %s: %s", info.artifact, str(err)[:300])
        return None
    log.info("ok    %s", info.artifact)
    return result


def run(ctx: Context) -> None:
    folder = ctx.paths.out / "smoke"
    folder.mkdir(parents=True, exist_ok=True)
    p = ctx.providers
    _try(
        ctx,
        CallInfo("smoke", "text", p.text.name, TEXT),
        lambda: p.text.complete(model=TEXT, prompt="Say: ready"),
    )
    spoken = _try(
        ctx,
        CallInfo("smoke", "speech-amharic", p.speech.name, SPEECH, {"voice": "Sulafat"}),
        lambda: p.speech.synthesise(
            model=SPEECH, voice="Sulafat", style="calm, warm, unhurried", text="ሰላም። ዛሬ አንድ ታሪክ እነግራችኋለሁ።"
        ),
    )
    if spoken:
        (folder / "speech.wav").write_bytes(spoken.data)
    _images(ctx)
    if ctx.providers.gpu.available():
        log.info("ok    gpu lane is configured (credentials are checked on the first submission)")
    else:
        log.info("SKIP  gpu lane: set KAGGLE_USERNAME plus a token")


def _images(ctx: Context) -> None:
    folder, image = ctx.paths.out / "smoke", ctx.providers.image
    prompt = "a clay pot on a low wooden stool, warm hand-painted gouache"
    plain = _try(
        ctx,
        CallInfo("smoke", "image", image.name, KLEIN, {"size": [512, 512]}, 7),
        lambda: image.generate(model=KLEIN, prompt=prompt, size=(512, 512), steps=4, seed=7, references=[]),
    )
    if not plain:
        return
    (folder / "image.png").write_bytes(plain.data)
    with_ref = _try(
        ctx,
        CallInfo(
            "smoke", "image-with-reference", image.name, KLEIN, {"size": list(PROBE_SIZE), "n_refs": 1}, 7
        ),
        lambda: image.generate(
            model=KLEIN,
            prompt="the same pot at dawn",
            size=PROBE_SIZE,
            steps=4,
            seed=7,
            references=[plain.data],
        ),
    )
    if with_ref:
        (folder / "image_ref.png").write_bytes(with_ref.data)
        got = Image.open(io.BytesIO(with_ref.data)).size
        log.info("      asked for %s, got %s", PROBE_SIZE, got)
