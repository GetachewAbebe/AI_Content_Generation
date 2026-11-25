"""Interfaces the stages depend on. A model is replaced by writing one class here, not by editing stages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ..core.runlog import ModelResult, RunLog


class SpeechProvider(Protocol):
    name: str

    def synthesise(self, *, model: str, voice: str, style: str, text: str) -> ModelResult: ...


class ImageProvider(Protocol):
    name: str

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        size: tuple[int, int],
        steps: int,
        seed: int,
        references: list[bytes],
    ) -> ModelResult: ...


class TextProvider(Protocol):
    name: str

    def complete(
        self, *, model: str, prompt: str, attachments: list[dict[str, str]] | None = None
    ) -> ModelResult: ...


class GpuLane(Protocol):
    """Runs a batch of jobs elsewhere and returns the folder holding whatever finished."""

    name: str

    def available(self) -> bool: ...

    def run_batch(
        self, kind: str, jobs: list[dict[str, Any]], files: dict[str, Path], runlog: RunLog
    ) -> Path: ...


@dataclass(frozen=True)
class Providers:
    speech: SpeechProvider
    image: ImageProvider
    text: TextProvider
    gpu: GpuLane
