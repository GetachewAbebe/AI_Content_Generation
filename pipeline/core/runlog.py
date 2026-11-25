"""runs.jsonl (one line per model call attempt) and the retry policy that feeds it."""

from __future__ import annotations

import datetime as dt
import json
import random
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import redact
from .errors import PermanentError, TransientError

MAX_DELAY_S = 120.0


def new_run_id() -> str:
    return dt.datetime.now().strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:4]


@dataclass
class ModelResult:
    """What a provider returns: the payload plus what the call consumed."""

    data: bytes
    units: dict[str, Any] = field(default_factory=dict)
    list_price_usd: float | None = None


@dataclass
class CallInfo:
    """What is being called, for the log."""

    stage: str
    artifact: str
    provider: str
    model: str
    params: dict[str, Any] = field(default_factory=dict)
    seed: int | None = None
    input_hash: str | None = None


class RunLog:
    def __init__(self, path: Path, run_id: str | None = None) -> None:
        self.path = path
        self.run_id = run_id or new_run_id()

    def write(self, call: CallInfo, *, status: str, latency_s: float, **extra: Any) -> None:
        line = {
            "ts": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            "run_id": self.run_id,
            "stage": call.stage,
            "artifact": call.artifact,
            "provider": call.provider,
            "model": call.model,
            "params": call.params,
            "seed": call.seed,
            "input_hash": call.input_hash,
            "attempt": 1,
            "status": status,
            "latency_s": round(latency_s, 3),
            "gpu_minutes": None,
            "units": {},
            "cost_usd": 0.0,
            "list_price_usd": None,
            "error": None,
            **extra,
        }
        if line["error"]:
            line["error"] = redact(str(line["error"]))[:600]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as handle:
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")

    def read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text().splitlines() if line]

    def call(
        self,
        info: CallInfo,
        func: Callable[[], ModelResult],
        *,
        attempts: int = 4,
        base_delay: float = 4.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> ModelResult:
        """Run `func`, retrying TransientError with backoff. Every attempt is logged."""
        for attempt in range(1, attempts + 1):
            start = time.monotonic()
            try:
                result = func()
            except PermanentError as err:
                self.write(
                    info, status="error", latency_s=time.monotonic() - start, attempt=attempt, error=err
                )
                raise
            except TransientError as err:
                delay = err.retry_after or base_delay * 2 ** (attempt - 1) + random.uniform(0, 1)
                give_up = attempt == attempts or delay > MAX_DELAY_S
                self.write(
                    info,
                    status="error" if give_up else "retry",
                    latency_s=time.monotonic() - start,
                    attempt=attempt,
                    error=err,
                )
                if give_up:
                    raise
                sleep(delay)
            else:
                self.write(
                    info,
                    status="ok",
                    latency_s=time.monotonic() - start,
                    attempt=attempt,
                    units=result.units,
                    list_price_usd=result.list_price_usd,
                )
                return result
        raise AssertionError("unreachable: the loop returns or raises")
