"""Deterministic stand-ins for every provider, used by `make mock` and the tests."""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import wave
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from ..core.runlog import ModelResult, RunLog
from .base import Providers


def _rng(*key: Any) -> np.random.Generator:
    return np.random.default_rng(int(hashlib.sha256(repr(key).encode()).hexdigest()[:8], 16))


def _wav(samples: np.ndarray, rate: int) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())
    return buffer.getvalue()


class FakeSpeech:
    name = "mock"

    def synthesise(self, *, model: str, voice: str, style: str, text: str) -> ModelResult:
        t = np.arange(int(max(1.2, len(text) / 14) * 24_000)) / 24_000
        tone = 0.25 * np.sin(2 * np.pi * 180 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 4 * t))
        return ModelResult(_wav(tone + 0.01 * _rng(text).standard_normal(t.size), 24_000))


class FakeImage:
    name = "mock"

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        size: tuple[int, int],
        steps: int,
        seed: int,
        references: list[bytes],
    ) -> ModelResult:
        pixels = _rng(prompt, seed).integers(30, 220, (6, 6, 3), dtype=np.uint8)
        buffer = io.BytesIO()
        Image.fromarray(pixels).resize(size, Image.Resampling.BICUBIC).save(buffer, "PNG")
        return ModelResult(buffer.getvalue())


class FakeText:
    name = "mock"

    def __init__(self, replies: list[str] | None = None) -> None:
        self.replies = list(replies or [])

    def complete(
        self, *, model: str, prompt: str, attachments: list[dict[str, str]] | None = None
    ) -> ModelResult:
        return ModelResult((self.replies.pop(0) if self.replies else "ready").encode())


class FakeGpu:
    """Produces real (tiny) media files and a GPU log, so the ingest code runs exactly as it will for Kaggle."""

    name = "mock"

    def __init__(self, root: Path, *, fail: tuple[str, ...] = (), online: bool = True) -> None:
        self.root, self.fail, self.online = root, fail, online
        self.batches: list[list[str]] = []

    def available(self) -> bool:
        return self.online

    def run_batch(
        self, kind: str, jobs: list[dict[str, Any]], files: dict[str, Path], runlog: RunLog
    ) -> Path:
        self.batches.append([job["name"] for job in jobs])
        dest = self.root / f"{kind}-{len(self.batches)}"
        dest.mkdir(parents=True, exist_ok=True)
        with (dest / "gpu_runs.jsonl").open("w") as handle:
            for job in jobs:
                ok = job["name"] not in self.fail
                if ok:
                    self._render(kind, job, dest)
                event = {"event": "item", "name": job["name"], "seconds": 60.0, "ok": ok, "attempt": 1}
                event["error"] = None if ok else "OutOfMemoryError: fake"
                handle.write(json.dumps(event) + "\n")
        return dest

    @staticmethod
    def _render(kind: str, job: dict[str, Any], dest: Path) -> None:
        if kind == "ace":
            t = np.arange(int(job["duration_s"] * 48_000)) / 48_000
            (dest / f"{job['name']}.wav").write_bytes(_wav(0.2 * np.sin(2 * np.pi * 220 * t), 48_000))
            return
        source = (
            f"testsrc2=s={job['width']}x{job['height']}:r={job['fps']}:d={job['num_frames'] / job['fps']}"
        )
        target = dest / f"{job['name']}.mp4"
        command = [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            source,
            "-pix_fmt",
            "yuv420p",
            str(target),
        ]
        subprocess.run(command, check=True)


def fake_providers(root: Path) -> Providers:
    return Providers(FakeSpeech(), FakeImage(), FakeText(), FakeGpu(root / "fake_gpu"))
