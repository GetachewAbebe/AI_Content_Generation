"""The shared logger."""

from __future__ import annotations

import logging
import sys

log = logging.getLogger("heritage")


def setup_logging() -> None:
    logging.basicConfig(
        stream=sys.stdout, level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S"
    )
