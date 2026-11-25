"""Thin FFmpeg wrapper."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from ..core.errors import PipelineError


def run(*args: object) -> str:
    """Run ffmpeg and return its stderr, where filters print their reports."""
    command = ["ffmpeg", "-hide_banner", "-nostdin", "-y", *map(str, args)]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise PipelineError(f"ffmpeg failed: {' '.join(command)[:600]}\n{result.stderr[-1500:]}")
    return result.stderr


def probe(path: Path) -> dict[str, Any]:
    command = ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]
    return json.loads(subprocess.run(command, capture_output=True, text=True, check=True).stdout)


def duration(path: Path) -> float:
    return float(probe(path)["format"]["duration"])
