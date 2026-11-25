"""Stage: script. Drafts storyboard.draft.json from story/brief.md; a person approves it as storyboard.json."""

from __future__ import annotations

import json
from pathlib import Path

from . import validate
from .core.config import ROOT, SCHEMA
from .core.context import Context
from .core.errors import PipelineError
from .core.log import log
from .core.runlog import CallInfo

MODEL = "gemini-3.8-flash"
MAX_ROUNDS = 3
EXAMPLE = ROOT / "tests" / "fixtures" / "storyboard.mock.json"


def _prompt(brief: str) -> str:
    return (
        f"Write a film storyboard as one JSON object that satisfies this JSON Schema:\n{SCHEMA.read_text()}\n\n"
        f"A structural example with dummy content (copy its technical settings, not its words):\n"
        f"{EXAMPLE.read_text()}\n\nUse only facts in this brief; invent no events:\n{brief}\n\nReturn JSON only."
    )


def _parse(text: str) -> tuple[object | None, list[str]]:
    try:
        data = json.loads(text[text.index("{") : text.rindex("}") + 1])
    except ValueError as err:
        return None, [f"not valid JSON: {err}"]
    return data, validate.check(data)


def run(ctx: Context, brief: Path = ROOT / "story" / "brief.md") -> Path:
    prompt = _prompt(brief.read_text())
    for round_no in range(1, MAX_ROUNDS + 1):
        info = CallInfo("script", f"draft{round_no}", ctx.providers.text.name, MODEL, {"round": round_no})
        asked = prompt
        reply = ctx.runlog.call(info, lambda p=asked: ctx.providers.text.complete(model=MODEL, prompt=p))  # type: ignore[misc]
        data, errors = _parse(reply.data.decode())
        if not errors:
            target = ctx.paths.base / "storyboard.draft.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
            log.info("wrote %s; review it, then save it as storyboard.json", target)
            return target
        log.info("draft %d rejected with %d error(s); asking for a repair", round_no, len(errors))
        prompt += "\n\nYour previous answer failed validation:\n" + "\n".join(errors[:20])
    raise PipelineError(f"no valid draft after {MAX_ROUNDS} rounds")
