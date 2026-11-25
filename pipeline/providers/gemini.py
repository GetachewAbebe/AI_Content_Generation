"""Gemini Interactions API: text and speech. Request shape read from the docs on 2026-11-25."""

from __future__ import annotations

import base64
from collections.abc import Iterator
from typing import Any

from ..core.config import require
from ..core.errors import PermanentError, TransientError
from ..core.runlog import ModelResult
from .http import post_json

URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
WAV_HEADER_BYTES = 44
BYTES_PER_SECOND = 24_000 * 2
AUDIO_TOKENS_PER_SECOND = 25
# USD per token, list price. Real spend on the free tier is zero.
LIST_PRICE: dict[str, tuple[float, float]] = {
    "gemini-3.8-flash-tts": (0.50e-6, 9.00e-6),
    "gemini-3.8-flash-lite-tts": (0.50e-6, 6.00e-6),
    "gemini-3.8-flash": (0.75e-6, 3.75e-6),
    "gemini-3.5-flash-lite": (0.30e-6, 2.50e-6),
}


def _blocks(body: dict[str, Any], kind: str) -> Iterator[dict[str, Any]]:
    for step in body.get("steps", []):
        if step.get("type") == "model_output":
            yield from (c for c in step.get("content", []) if c.get("type") == kind)


def _usage(body: dict[str, Any]) -> dict[str, Any]:
    usage = body.get("usage") or {}
    return {
        "input_tokens": usage.get("total_input_tokens") or usage.get("input_tokens"),
        "output_tokens": usage.get("total_output_tokens") or usage.get("output_tokens"),
    }


def _list_price(model: str, units: dict[str, Any], estimated_output: float | None = None) -> float | None:
    output = units.get("output_tokens") or estimated_output
    if model not in LIST_PRICE or output is None:
        return None
    price_in, price_out = LIST_PRICE[model]
    return round((units.get("input_tokens") or 0) * price_in + output * price_out, 6)


class Gemini:
    name = "gemini"

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        return post_json(
            URL, json={"store": False, **body}, headers={"x-goog-api-key": require("GEMINI_API_KEY")}
        )

    def synthesise(self, *, model: str, voice: str, style: str, text: str) -> ModelResult:
        content = {"type": "text", "text": text, "annotations": [{"type": "speech_metadata", "style": style}]}
        body = self._post(
            {
                "model": model,
                "input": [{"type": "user_input", "content": [content]}],
                "response_format": {"type": "audio", "mime_type": "audio/wav", "sample_rate": 24000},
                "generation_config": {"speech_config": [{"voice": voice}]},
            }
        )
        audio = list(_blocks(body, "audio"))
        if not audio:
            raise TransientError(f"no audio in response (status={body.get('status')})")
        wav = base64.b64decode(audio[-1]["data"])
        if wav[:4] != b"RIFF":
            raise PermanentError("expected WAV audio, got another container")
        seconds = max(0.0, (len(wav) - WAV_HEADER_BYTES) / BYTES_PER_SECOND)
        units = {**_usage(body), "audio_s": round(seconds, 3)}
        return ModelResult(wav, units, _list_price(model, units, seconds * AUDIO_TOKENS_PER_SECOND))

    def complete(
        self, *, model: str, prompt: str, attachments: list[dict[str, str]] | None = None
    ) -> ModelResult:
        content = [{"type": "text", "text": prompt}, *(attachments or [])]
        body = self._post({"model": model, "input": [{"type": "user_input", "content": content}]})
        text = "".join(block.get("text", "") for block in _blocks(body, "text"))
        if not text:
            raise TransientError(f"no text in response (status={body.get('status')})")
        units = _usage(body)
        return ModelResult(text.encode(), units, _list_price(model, units))
