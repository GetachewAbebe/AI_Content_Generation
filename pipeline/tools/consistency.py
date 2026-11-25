"""Score every keyframe against the reference sheet with a vision model. A cheap first screen, not a verdict."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from ..core.cache import digest, file_digest
from ..core.context import Context
from ..core.errors import PipelineError
from ..core.log import log
from ..core.runlog import CallInfo
from ..core.storyboard import Shot, Storyboard

MODEL = "gemini-3.8-flash"
PROMPT = (
    "Image 1 is a reference sheet. Image 2 is a film keyframe. Score 1 (different) to 5 (same) and reply with JSON "
    'only: {"identity": n, "clothing": n, "style": n, "hands_ok": true|false, "face_ok": true|false, "notes": "..."}. '
    "If no person is visible, set identity and clothing to null."
)


def _image(path: Path) -> dict[str, str]:
    return {"type": "image", "mime_type": "image/png", "data": base64.b64encode(path.read_bytes()).decode()}


def _score(ctx: Context, reference: Path, frame: Path, name: str) -> dict[str, Any]:
    key = digest([file_digest(reference), file_digest(frame), PROMPT, MODEL])
    info = CallInfo("consistency", name, ctx.providers.text.name, MODEL, input_hash=key)
    reply = ctx.runlog.call(
        info,
        lambda: ctx.providers.text.complete(
            model=MODEL, prompt=PROMPT, attachments=[_image(reference), _image(frame)]
        ),
    )
    text = reply.data.decode()
    try:
        return {"key": key, **json.loads(text[text.index("{") : text.rindex("}") + 1])}
    except ValueError:
        return {"key": key, "notes": f"unparsable reply: {text[:120]}"}


def _targets(ctx: Context, sb: Storyboard) -> list[tuple[Shot, str, Path, Path]]:
    return [
        (
            shot,
            aspect,
            ctx.paths.reference(shot["keyframe"]["references"][0]),
            ctx.paths.keyframe(shot["id"], aspect),
        )
        for shot in sb["shots"]
        if shot["keyframe"]["references"]
        for aspect in ("vertical", "horizontal")
    ]


def run(ctx: Context, sb: Storyboard) -> None:
    out = ctx.paths.out / "eval" / "consistency.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    scores: dict[str, Any] = json.loads(out.read_text()) if out.exists() else {}
    for shot, aspect, reference, frame in _targets(ctx, sb):
        name = f"{shot['id']}.{aspect}"
        if not frame.exists():
            continue
        key = digest([file_digest(reference), file_digest(frame), PROMPT, MODEL])
        if scores.get(name, {}).get("key") == key:
            continue
        try:
            scores[name] = _score(ctx, reference, frame, name)
        except PipelineError as err:
            log.info("consistency %s failed: %s", name, str(err)[:120])
            continue
        out.write_text(json.dumps(scores, indent=1, ensure_ascii=False) + "\n")
        log.info("consistency %s: %s", name, {k: v for k, v in scores[name].items() if k != "key"})
