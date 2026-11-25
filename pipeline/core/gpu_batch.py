"""Shared by the shots and music stages: submit jobs, cache what finished, replay the GPU log once."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import cache
from .context import Context
from .errors import MissingCredentialError, PermanentError, TransientError
from .log import log
from .runlog import CallInfo

Job = dict[str, Any]
MAX_ROUNDS = 3


def _events(dest: Path) -> list[dict[str, Any]]:
    path = dest / "gpu_runs.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line] if path.exists() else []


def _replay(ctx: Context, stage: str, dest: Path, jobs: dict[str, Job], model: str) -> None:
    marker = dest / ".logged"
    if marker.exists():
        return
    for event in _events(dest):
        job = jobs.get(event.get("name", ""), {})
        measured = {
            k: v for k, v in event.items() if k not in ("event", "name", "seconds", "ok", "error", "attempt")
        }
        info = CallInfo(
            stage if job else f"{stage}_{event['event']}",
            event.get("name") or event["event"],
            ctx.providers.gpu.name,
            model,
            {**job, "measured": measured},
            job.get("seed"),
            cache.digest(job) if job else None,
        )
        ctx.runlog.write(
            info,
            status="ok" if event["ok"] else "error",
            latency_s=event["seconds"],
            attempt=event.get("attempt", 1),
            gpu_minutes=round(event["seconds"] / 60, 2),
            error=event.get("error"),
        )
    marker.touch()


def _ingest(stage: str, dest: Path, jobs: dict[str, Job], target: Callable[[Job], Path], suffix: str) -> int:
    finished = {e["name"]: e for e in _events(dest) if e.get("name") and e["ok"]}
    done = 0
    for name, job in jobs.items():
        source = dest / f"{name}{suffix}"
        if not source.exists():
            continue
        with cache.atomic(target(job)) as temp:
            shutil.copy(source, temp)
        # the worker may have shortened a clip after running out of memory: keep what it really made
        cache.record(target(job), job, provider="gpu", stage=stage, actual=finished.get(name, {}))
        done += 1
    return done


def run_jobs(
    ctx: Context,
    stage: str,
    kind: str,
    jobs: list[Job],
    files: Callable[[list[Job]], dict[str, Path]],
    target: Callable[[Job], Path],
    suffix: str,
) -> None:
    """Best effort: leaves unfinished jobs uncached so the caller can fall back and a later run can retry."""
    pending = [job for job in jobs if not cache.is_fresh(target(job), job)]
    if not pending or not ctx.allow_gpu:
        return
    if not ctx.providers.gpu.available():
        log.info("%s: no GPU lane configured, using fallbacks", stage)
        return
    for _ in range(MAX_ROUNDS):
        named = {job["name"]: job for job in pending}
        try:
            dest = ctx.providers.gpu.run_batch(kind, pending, files(pending), ctx.runlog)
        except (MissingCredentialError, PermanentError, TransientError) as err:
            log.info("%s: GPU lane failed, using fallbacks: %s", stage, err)
            return
        _replay(ctx, stage, dest, named, pending[0]["model"])
        done = _ingest(stage, dest, named, target, suffix)
        pending = [job for job in pending if not cache.is_fresh(target(job), job)]
        if not pending or not done:
            return
