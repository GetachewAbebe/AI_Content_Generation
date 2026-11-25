import json

import numpy as np
import pytest

from pipeline import assemble, cli, narration, timeline
from pipeline.core.config import SAMPLE_RATE, Paths
from pipeline.core.errors import TimingError
from pipeline.media import audio, picture, subtitles
from pipeline.tools import consistency, costs, duck_sweep, showcase, smoke, tts_bench


def test_subtitles_fit_and_fill_the_speech():
    events = timeline.subtitles("s", "word " * 60, 1.0, 9.0)
    assert all(len(e.lines) <= 2 and max(map(len, e.lines)) <= 40 for e in events)
    assert events[0].start == 1.0
    assert events[-1].end == pytest.approx(10.0, abs=0.01)


def test_cuts_land_on_beats_and_whole_frames(ctx, sb):
    narration.run(ctx, sb)
    beat = 60 / 66
    for shot in timeline.build(ctx, sb).shots[:5]:
        assert shot.end * 24 == pytest.approx(round(shot.end * 24))
        assert abs(shot.end / beat - round(shot.end / beat)) * beat <= 1 / 48 + 1e-6


def test_a_film_outside_the_limits_is_refused(ctx, sb):
    for shot in sb["shots"]:
        shot["min_duration_s"] = 12
    narration.run(ctx, sb)
    with pytest.raises(TimingError):
        timeline.build(ctx, sb)


def test_times_roll_over():
    assert subtitles.srt_time(59.9996) == "00:01:00,000"
    assert subtitles.ass_time(59.996) == "0:01:00.00"


def test_loop_reaches_the_length_without_a_jump():
    tone = np.sin(2 * np.pi * 100 * np.arange(SAMPLE_RATE * 5) / SAMPLE_RATE).astype(np.float32)
    out = audio.loop_to(tone, SAMPLE_RATE * 13)
    assert out.size == SAMPLE_RATE * 13
    assert np.abs(np.diff(out)).max() < 0.05


@pytest.mark.parametrize("move", ["push_in", "pull_out", "pan_left", "pan_right", "tilt_up", "tilt_down"])
def test_every_move_in_the_schema_exists(move):
    assert len(picture.kenburns(move, 100)) == 3


def test_end_card_draws_both_scripts():
    image = picture.draw_end_card(["የሙከራ ርዕስ", "This film was made with AI."], "vertical")
    assert np.asarray(image).std() > 1


def test_character_error_rate():
    assert tts_bench.character_error_rate("ሰላም።", "ሰላም") == 0
    assert tts_bench.character_error_rate("abcd", "abxd") == 0.25
    assert tts_bench.character_error_rate("ab", "") == 1


def test_tools_run_on_fakes(ctx, sb):
    from pipeline import keyframes

    narration.run(ctx, sb)
    keyframes.run(ctx, sb)
    smoke.run(ctx)
    tts_bench.run(ctx)
    consistency.run(ctx, sb)
    duck_sweep.run(ctx, sb)
    showcase.run(ctx, sb)
    costs.run(ctx)
    assert "| narration |" in (ctx.paths.base / "COSTS.md").read_text()
    assert len(json.loads((ctx.paths.out / "eval" / "duck_sweep.json").read_text())) == 5
    assert "made with AI" in (ctx.paths.final / "index.html").read_text()


@pytest.mark.slow
def test_radio_cut(ctx, sb):
    narration.run(ctx, sb)
    assert assemble.radio(ctx, sb).exists()


@pytest.mark.slow
def test_whole_film_through_the_command_line(monkeypatch, tmp_path):
    """Every stage, both exports, all checks green, and a second run that makes no model calls."""
    from tests.conftest import FIXTURE

    monkeypatch.setattr(cli, "ROOT", tmp_path)
    args = ["film", "--mock", "--storyboard", str(FIXTURE)]
    assert cli.main(args) == 0
    paths = Paths(tmp_path / "build" / "mock")
    report = json.loads((paths.final / "qc.json").read_text())
    assert all(c["ok"] for c in report["checks"])
    assert set(report["shot_sources"].values()) == {"wan", "kenburns"}
    calls = len(paths.runs.read_text().splitlines())
    assert cli.main(args) == 0
    assert len(paths.runs.read_text().splitlines()) == calls


def test_errors_are_reported_not_raised(tmp_path):
    assert cli.main(["validate", "--mock", "--storyboard", str(tmp_path / "none.json")]) == 1
