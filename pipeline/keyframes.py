"""Stage: keyframes. Reference sheet first, then one keyframe per shot and aspect, conditioned on it."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .core import cache
from .core.context import Context
from .core.log import log
from .core.runlog import CallInfo, ModelResult
from .core.storyboard import Storyboard

SIZES = {"vertical": (720, 1280), "horizontal": (1280, 720), "square": (1024, 1024)}
FRAMING = {
    "vertical": "Vertical 9:16 composition, main subject centred.",
    "horizontal": "Horizontal 16:9 composition of the same scene, main subject centred.",
    "square": "",
}
NO_TEXT = "No text, no lettering, no watermark."


@dataclass(frozen=True)
class ImageTask:
    stage: str
    artifact: str
    target: Path
    prompt: str
    seed: int
    aspect: str
    references: list[Path]


def build_prompt(sb: Storyboard, text: str, character_ids: list[str], aspect: str) -> str:
    """The style block and character descriptions are repeated verbatim in every prompt to limit drift."""
    described = {c["id"]: c["description"] for c in sb["characters"]}
    parts = [text, *(described[c] for c in character_ids), FRAMING[aspect], sb["style_block"], NO_TEXT]
    return " ".join(part.strip() for part in parts if part.strip())


def reference_tasks(ctx: Context, sb: Storyboard) -> list[ImageTask]:
    return [
        ImageTask(
            "reference",
            ref["id"],
            ctx.paths.reference(ref["id"]),
            build_prompt(sb, ref["prompt"], ref.get("characters", []), "square"),
            ref["seed"],
            "square",
            [ctx.paths.reference(x) for x in ref.get("references", [])],
        )
        for ref in sb["references"]
    ]


def keyframe_tasks(ctx: Context, sb: Storyboard) -> list[ImageTask]:
    tasks = []
    for shot in sb["shots"]:
        frame = shot["keyframe"]
        sheet = [ctx.paths.reference(x) for x in frame["references"]]
        for aspect in ("vertical", "horizontal"):
            # 16:9 sees the finished 9:16 frame first, so both exports show the same scene
            lead = [ctx.paths.keyframe(shot["id"], "vertical")] if aspect == "horizontal" else []
            tasks.append(
                ImageTask(
                    "keyframe",
                    f"{shot['id']}.{aspect}",
                    ctx.paths.keyframe(shot["id"], aspect),
                    build_prompt(sb, frame["prompt"], frame["characters"], aspect),
                    frame["seed"],
                    aspect,
                    lead + sheet,
                )
            )
    return tasks


def execute(ctx: Context, sb: Storyboard, task: ImageTask) -> int:
    image, size = sb["providers"]["image"], SIZES[task.aspect]
    wanted = {
        "stage": task.stage,
        "model": image["model"],
        "steps": image["steps"],
        "prompt": task.prompt,
        "seed": task.seed,
        "size": list(size),
        "references": [cache.file_digest(p) for p in task.references],
    }
    if cache.is_fresh(task.target, wanted):
        return 0
    log.info("%s %s: generating", task.stage, task.artifact)
    info = CallInfo(
        task.stage,
        task.artifact,
        ctx.providers.image.name,
        image["model"],
        {"steps": image["steps"], "size": list(size), "n_refs": len(task.references), "prompt": task.prompt},
        task.seed,
        cache.digest(wanted),
    )

    def generate() -> ModelResult:
        return ctx.providers.image.generate(
            model=image["model"],
            prompt=task.prompt,
            size=size,
            steps=image["steps"],
            seed=task.seed,
            references=[p.read_bytes() for p in task.references],
        )

    result = ctx.runlog.call(info, generate)
    cache.store(task.target, result.data, wanted, run_id=ctx.runlog.run_id)
    return 1


def run(ctx: Context, sb: Storyboard) -> int:
    # references are executed first because keyframe hashes read them from disk
    calls = sum(execute(ctx, sb, task) for task in reference_tasks(ctx, sb))
    return calls + sum(execute(ctx, sb, task) for task in keyframe_tasks(ctx, sb))
