"""Ceiling work: how intelligible is the TTS in Amharic, Tigrinya, Somali and Afaan Oromo?

Round trip: speak a sentence, ask a different model to transcribe the audio, and measure character error rate.
The judge is imperfect and from the same vendor, so a native speaker's rating column sits beside the number.
"""

from __future__ import annotations

import base64
import json
import unicodedata
from typing import Any

from ..core.cache import digest
from ..core.config import ROOT
from ..core.context import Context
from ..core.errors import PipelineError
from ..core.log import log
from ..core.runlog import CallInfo, ModelResult

SENTENCES = ROOT / "experiments" / "tts_sentences.json"
SPEECH, JUDGE, VOICE, STYLE = "gemini-3.8-flash-tts", "gemini-3.8-flash", "Sulafat", "calm, warm, unhurried"


def normalise(text: str) -> str:
    """Compare letters only: punctuation, spacing and case are not pronunciation errors."""
    return "".join(
        c for c in unicodedata.normalize("NFC", text).lower() if unicodedata.category(c)[0] in "LM"
    )


def character_error_rate(expected: str, heard: str) -> float:
    a, b = normalise(expected), normalise(heard)
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        current = [i]
        for j, y in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[-1] + 1, previous[j - 1] + (x != y)))
        previous = current
    return previous[-1] / max(1, len(a))


def _measure(ctx: Context, item: dict[str, Any]) -> dict[str, Any]:
    name = item["id"]
    speech, text = ctx.providers.speech, ctx.providers.text

    def speak() -> ModelResult:
        return speech.synthesise(model=SPEECH, voice=VOICE, style=STYLE, text=item["text"])

    audio = ctx.runlog.call(CallInfo("tts_bench", name, speech.name, SPEECH, {"lang": item["lang"]}), speak)
    wav = ctx.paths.out / "eval" / "tts" / f"{name}.wav"
    wav.parent.mkdir(parents=True, exist_ok=True)
    wav.write_bytes(audio.data)
    block = {"type": "audio", "mime_type": "audio/wav", "data": base64.b64encode(audio.data).decode()}
    # the prompt names the language but never contains the sentence
    ask = (
        f"Transcribe this {item['language']} speech exactly, in its usual script. Return the transcript only."
    )

    def listen() -> ModelResult:
        return text.complete(model=JUDGE, prompt=ask, attachments=[block])

    heard = ctx.runlog.call(
        CallInfo("tts_bench_judge", name, text.name, JUDGE, {"lang": item["lang"]}), listen
    )
    transcript = heard.data.decode().strip()
    return {**item, "heard": transcript, "cer": round(character_error_rate(item["text"], transcript), 3)}


def run(ctx: Context) -> None:
    out = ctx.paths.out / "eval" / "tts_bench.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = json.loads(out.read_text()) if out.exists() else {}
    for item in json.loads(SENTENCES.read_text()):
        key = digest([item["text"], SPEECH, JUDGE, VOICE, STYLE])
        if results.get(item["id"], {}).get("key") == key:
            continue
        try:
            results[item["id"]] = {"key": key, **_measure(ctx, item)}
        except PipelineError as err:
            results[item["id"]] = {**item, "error": str(err)[:200]}
        out.write_text(json.dumps(results, indent=1, ensure_ascii=False) + "\n")
        log.info("%s: %s", item["id"], results[item["id"]].get("cer", results[item["id"]].get("error")))
