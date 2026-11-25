"""Everything a stage needs, passed in explicitly. Tests and mock runs swap the parts."""

from __future__ import annotations

from dataclasses import dataclass

from ..providers.base import Providers
from .config import Paths
from .runlog import RunLog


@dataclass(frozen=True)
class Context:
    paths: Paths
    runlog: RunLog
    providers: Providers
    allow_gpu: bool = True
