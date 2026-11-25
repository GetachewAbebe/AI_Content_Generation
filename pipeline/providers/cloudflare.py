"""Cloudflare Workers AI images: FLUX.2 klein (references) and FLUX.1 schnell (no references)."""

from __future__ import annotations

import base64
import io
import math
from typing import Any

from PIL import Image

from ..core.config import require
from ..core.errors import PermanentError
from ..core.runlog import ModelResult
from .http import post_json

BASE = "https://api.cloudflare.com/client/v4/accounts"
USD_PER_NEURON = 0.011 / 1000
KLEIN_OUTPUT_TILE, KLEIN_INPUT_TILE = 26.05, 5.37
SCHNELL_TILE, SCHNELL_STEP, SCHNELL_TILES = 4.80, 9.60, 4
MAX_REFERENCES, MAX_REFERENCE_EDGE = 4, 496  # documented as under 512x512 for klein 9B


def shrink(png: bytes, edge: int = MAX_REFERENCE_EDGE) -> bytes:
    image = Image.open(io.BytesIO(png)).convert("RGB")
    image.thumbnail((edge, edge))
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


class Cloudflare:
    name = "cloudflare"

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
        url = f"{BASE}/{require('CLOUDFLARE_ACCOUNT_ID')}/ai/run/{model}"
        headers = {"Authorization": f"Bearer {require('CLOUDFLARE_API_TOKEN')}"}
        if "flux-2" in model:
            used = references[:MAX_REFERENCES]
            body = post_json(url, headers=headers, files=self._form(prompt, size, steps, seed, used))
            tiles = math.ceil(size[0] / 512) * math.ceil(size[1] / 512)
            neurons = tiles * KLEIN_OUTPUT_TILE + len(used) * KLEIN_INPUT_TILE
        elif references:
            raise PermanentError(f"{model} cannot take reference images")
        else:
            body = post_json(url, headers=headers, json={"prompt": prompt[:2048], "steps": min(steps, 8)})
            neurons = SCHNELL_TILES * SCHNELL_TILE + steps * SCHNELL_STEP
        encoded = (body.get("result") or {}).get("image") or body.get("image")
        if not encoded:
            raise PermanentError(f"no image in response: {str(body)[:300]}")
        return ModelResult(
            base64.b64decode(encoded), {"neurons_est": round(neurons, 1)}, round(neurons * USD_PER_NEURON, 6)
        )

    @staticmethod
    def _form(
        prompt: str, size: tuple[int, int], steps: int, seed: int, references: list[bytes]
    ) -> list[Any]:
        fields = {"prompt": prompt, "width": size[0], "height": size[1], "steps": steps, "seed": seed}
        form: list[Any] = [(key, (None, str(value))) for key, value in fields.items()]
        form += [
            (f"input_image_{i}", (f"ref{i}.png", shrink(b), "image/png")) for i, b in enumerate(references)
        ]
        return form
