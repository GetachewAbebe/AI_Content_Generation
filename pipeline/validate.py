"""Storyboard validation: JSON Schema, then cross-references a schema cannot express, then consent."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator

from .core.config import ROOT, SCHEMA
from .core.errors import StoryboardError
from .core.storyboard import Storyboard


def schema_errors(data: Any) -> list[str]:
    validator = Draft202012Validator(json.loads(SCHEMA.read_text()))
    found = sorted(validator.iter_errors(data), key=lambda e: [str(p) for p in e.absolute_path])
    return [f"{'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message}" for e in found]


def _duplicates(sb: Storyboard) -> Iterator[str]:
    groups = {
        "shot": [s["id"] for s in sb["shots"]],
        "reference": [r["id"] for r in sb["references"]],
        "character": [c["id"] for c in sb["characters"]],
        "cue": [c["id"] for c in sb["music"]["cues"]],
    }
    for name, ids in groups.items():
        if len(set(ids)) != len(ids):
            yield f"duplicate {name} id"


def _unknown(owner: str, kind: str, used: list[str], known: set[str]) -> Iterator[str]:
    for name in used:
        if name not in known:
            yield f"{owner}: unknown {kind} '{name}'"


def _links(sb: Storyboard) -> Iterator[str]:
    characters = {c["id"] for c in sb["characters"]}
    declared: set[str] = set()
    for ref in sb["references"]:
        owner = f"reference {ref['id']}"
        yield from _unknown(owner, "or later reference", ref.get("references", []), declared)
        yield from _unknown(owner, "character", ref.get("characters", []), characters)
        declared.add(ref["id"])
    for shot in sb["shots"]:
        owner, frame = f"shot {shot['id']}", shot["keyframe"]
        yield from _unknown(owner, "reference", frame["references"], declared)
        yield from _unknown(owner, "character", frame["characters"], characters)


def _narration(sb: Storyboard) -> Iterator[str]:
    for shot in sb["shots"]:
        line = shot["narration"]
        if bool(line["text"].strip()) != bool(line["subtitle_en"].strip()):
            yield f"shot {shot['id']}: narration and subtitle must both be present or both be empty"


def _cues(sb: Storyboard) -> Iterator[str]:
    ids = [s["id"] for s in sb["shots"]]
    last = -1
    for cue in sb["music"]["cues"]:
        if cue["chosen_seed"] not in cue["seeds"]:
            yield f"cue {cue['id']}: chosen_seed must be one of seeds"
        if cue["start_shot"] not in ids:
            yield f"cue {cue['id']}: unknown start_shot"
            continue
        position = ids.index(cue["start_shot"])
        if position <= last:
            yield f"cue {cue['id']}: cues must be in shot order"
        last = position
    if sb["music"]["cues"][0]["start_shot"] != ids[0]:
        yield "first music cue must start on the first shot"


def _consent(sb: Storyboard, ethics: str) -> Iterator[str]:
    for person in sb["characters"]:
        if person["real_person"] and f"CONSENT-RECORD: {person.get('consent_id')}" not in ethics:
            yield f"character {person['id']} is real but ETHICS.md has no CONSENT-RECORD for them"


def check(data: Any, ethics_text: str | None = None) -> list[str]:
    errors = schema_errors(data)
    if errors:
        return errors
    sb = cast(Storyboard, data)
    if ethics_text is None:
        ethics = ROOT / "ETHICS.md"
        ethics_text = ethics.read_text() if ethics.exists() else ""
    errors = [*_duplicates(sb), *_links(sb), *_narration(sb), *_cues(sb), *_consent(sb, ethics_text)]
    if not any("AI" in line for line in sb["end_card"]["lines"]):
        errors.append("end_card must state that the film was made with AI")
    return errors


def load(path: Path) -> Storyboard:
    if not path.exists():
        raise StoryboardError(f"{path} does not exist")
    try:
        data = json.loads(path.read_text())
    except ValueError as err:
        raise StoryboardError(f"{path} is not valid JSON: {err}") from err
    errors = check(data)
    if errors:
        raise StoryboardError("storyboard is invalid:\n  - " + "\n  - ".join(errors))
    return cast(Storyboard, data)
