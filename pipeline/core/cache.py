"""Content-addressed cache: an artifact is valid only for the exact inputs that made it."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any


def digest(inputs: Any) -> str:
    text = json.dumps(inputs, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode()).hexdigest()


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def meta_path(path: Path) -> Path:
    return path.with_name(path.name + ".meta.json")


def read_meta(path: Path) -> dict[str, Any]:
    meta = meta_path(path)
    return json.loads(meta.read_text()) if meta.exists() else {}


def is_fresh(path: Path, inputs: Any) -> bool:
    """True if the file came from exactly these inputs and has not been altered since."""
    if not path.exists():
        return False
    meta = read_meta(path)
    return meta.get("input_hash") == digest(inputs) and meta.get("output_sha256") == file_digest(path)


@contextlib.contextmanager
def atomic(path: Path) -> Iterator[Path]:
    """Yield a temporary name and rename on success, so an interrupted run leaves no half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".tmp-{uuid.uuid4().hex[:6]}-{path.name}")
    try:
        yield temp
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def record(path: Path, inputs: Any, **extra: Any) -> None:
    """Write the sidecar that marks `path` as the result of `inputs`."""
    meta = {"input_hash": digest(inputs), "output_sha256": file_digest(path), "inputs": inputs, **extra}
    meta_path(path).write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n")


def store(path: Path, data: bytes, inputs: Any, **extra: Any) -> None:
    with atomic(path) as temp:
        temp.write_bytes(data)
    record(path, inputs, **extra)
