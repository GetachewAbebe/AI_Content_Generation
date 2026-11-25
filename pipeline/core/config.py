"""Paths, constants and secrets."""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .errors import MissingCredentialError


def find_root() -> Path:
    """The repository: HERITAGE_HOME, else the checkout holding this file, else the current folder."""
    home = os.environ.get("HERITAGE_HOME")
    if home:
        return Path(home).resolve()
    checkout = Path(__file__).resolve().parents[2]
    return checkout if (checkout / "schema").is_dir() else Path.cwd()


ROOT = find_root()
SCHEMA = ROOT / "schema" / "storyboard.schema.json"
FONTS = ROOT / "assets" / "fonts"
FPS = 24
SAMPLE_RATE = 48_000
ASPECTS: dict[str, tuple[int, int]] = {"vertical": (1080, 1920), "horizontal": (1920, 1080)}
SECRET_NAMES = ("GEMINI_API_KEY", "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID", "KAGGLE_API_TOKEN")


@dataclass(frozen=True)
class Paths:
    """Where one run reads and writes. Mock runs use a different base, so they cannot touch real logs."""

    base: Path

    @property
    def out(self) -> Path:
        return self.base / "outputs"

    @property
    def runs(self) -> Path:
        return self.base / "runs.jsonl"

    @property
    def final(self) -> Path:
        return self.out / "final"

    @property
    def audio(self) -> Path:
        return self.out / "audio"

    @property
    def remote(self) -> Path:
        return self.out / "remote"

    def narration(self, shot_id: str) -> Path:
        return self.out / "narration" / f"{shot_id}.wav"

    def reference(self, ref_id: str) -> Path:
        return self.out / "references" / f"{ref_id}.png"

    def keyframe(self, shot_id: str, aspect: str) -> Path:
        return self.out / "keyframes" / f"{shot_id}.{aspect}.png"

    def clip(self, shot_id: str, aspect: str) -> Path:
        return self.out / "clips" / f"{shot_id}.{aspect}.mp4"

    def score(self, cue_id: str, take: int | str) -> Path:
        return self.out / "music" / f"{cue_id}.{take}.wav"

    def segment(self, name: str, aspect: str) -> Path:
        return self.out / "segments" / f"{name}.{aspect}.mp4"

    def film(self, aspect: str) -> Path:
        return self.final / f"film.{aspect}.mp4"


def load_env(path: Path = ROOT / ".env") -> None:
    """Read KEY=value lines into the environment without overriding what is already set."""
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip("'\"")
        if value:
            os.environ.setdefault(key.strip(), value)


def require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise MissingCredentialError(f"{name} is not set. Copy .env.example to .env and fill it in.")
    return value


def redact(text: str, names: Iterable[str] = SECRET_NAMES) -> str:
    """Replace secret values with their names before anything is printed or logged."""
    for name in names:
        value = os.environ.get(name)
        if value:
            text = text.replace(value, f"<{name}>")
    return text
