import pytest

from pipeline import validate
from pipeline.core.errors import StoryboardError


def test_fixture_is_valid(sb):
    assert validate.check(sb) == []


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda s: s["shots"][0].pop("reason"), "reason"),
        (lambda s: s.update(shots=s["shots"][:5]), "shots"),
        (lambda s: s["shots"][1].update(id="s01"), "duplicate shot"),
        (lambda s: s["shots"][0]["keyframe"].update(references=["ghost"]), "unknown reference"),
        (lambda s: s["shots"][0]["keyframe"].update(characters=["ghost"]), "unknown character"),
        (lambda s: s["references"][0].update(references=["later"]), "unknown or later reference"),
        (lambda s: s["music"]["cues"][0].update(chosen_seed=99), "chosen_seed"),
        (lambda s: s["music"]["cues"][0].update(start_shot="s02"), "first music cue"),
        (lambda s: s["end_card"].update(lines=["Thank you"]), "AI"),
        (lambda s: s["shots"][0]["narration"].update(subtitle_en=""), "subtitle"),
        (lambda s: s["duration_s"].update(max=120), "90"),
        (lambda s: s.update(surprise=1), "surprise"),
    ],
)
def test_bad_storyboards_are_rejected(sb, mutate, expected):
    mutate(sb)
    assert any(expected in error for error in validate.check(sb))


def test_real_person_needs_a_consent_record(sb):
    sb["characters"][0].update(real_person=True, consent_id="c1")
    assert any("CONSENT-RECORD" in e for e in validate.check(sb, ethics_text=""))
    assert validate.check(sb, ethics_text="CONSENT-RECORD: c1") == []


def test_unreadable_files_raise_a_clear_error(tmp_path):
    bad = tmp_path / "x.json"
    bad.write_text("{")
    for path in (bad, tmp_path / "missing.json"):
        with pytest.raises(StoryboardError):
            validate.load(path)
