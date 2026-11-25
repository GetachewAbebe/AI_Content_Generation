import json

import pytest

from pipeline import keyframes, music, narration, script, shots
from pipeline.core import cache
from pipeline.core.errors import PipelineError
from pipeline.providers.fake import FakeGpu, FakeText

NARRATION, REFERENCES, KEYFRAMES, CLIPS, TRACKS = 9, 1, 18, 10, 5


def artifacts(ctx, since=0):
    return [line["artifact"] for line in ctx.runlog.read()[since:]]


def test_second_run_makes_no_calls(ctx, sb):
    assert narration.run(ctx, sb) == NARRATION
    assert keyframes.run(ctx, sb) == REFERENCES + KEYFRAMES
    assert narration.run(ctx, sb) == keyframes.run(ctx, sb) == 0


def test_one_narration_line_is_one_call(ctx, sb):
    narration.run(ctx, sb)
    keyframes.run(ctx, sb)
    before = len(ctx.runlog.read())
    sb["shots"][3]["narration"]["text"] += " አዲስ"
    narration.run(ctx, sb)
    keyframes.run(ctx, sb)
    assert artifacts(ctx, before) == ["s04"]


def test_one_keyframe_prompt_touches_only_that_shot(ctx, sb):
    keyframes.run(ctx, sb)
    before = len(ctx.runlog.read())
    sb["shots"][5]["keyframe"]["prompt"] += " At dusk."
    keyframes.run(ctx, sb)
    assert artifacts(ctx, before) == ["s06.vertical", "s06.horizontal"]


def test_changing_the_reference_sheet_invalidates_its_dependents(ctx, sb):
    keyframes.run(ctx, sb)
    sb["references"][0]["prompt"] += " Changed."
    assert keyframes.run(ctx, sb) == REFERENCES + KEYFRAMES


def test_tampered_output_is_regenerated(ctx, sb):
    narration.run(ctx, sb)
    ctx.paths.narration("s02").write_bytes(b"x")
    assert narration.run(ctx, sb) == 1


def test_clips_are_cached_and_gpu_minutes_logged_once(ctx, sb):
    keyframes.run(ctx, sb)
    clips = shots.run(ctx, sb)
    assert sum(c is not None for c in clips.values()) == CLIPS
    shots.run(ctx, sb)
    logged = [x for x in ctx.runlog.read() if x["stage"] == "shot"]
    assert len(logged) == CLIPS
    assert all(x["gpu_minutes"] == 1.0 for x in logged)
    assert len(ctx.providers.gpu.batches) == 1


def test_a_changed_keyframe_resubmits_only_its_own_clips(ctx, sb):
    keyframes.run(ctx, sb)
    shots.run(ctx, sb)
    sb["shots"][0]["keyframe"]["prompt"] += " At dusk."
    keyframes.run(ctx, sb)
    shots.run(ctx, sb)
    assert sorted(ctx.providers.gpu.batches[-1]) == ["s01.horizontal", "s01.vertical"]


def test_failed_clip_falls_back_alone_and_is_retried_later(make_ctx, sb, tmp_path):
    ctx = make_ctx(gpu=FakeGpu(tmp_path / "a", fail=("s03.vertical",)))
    keyframes.run(ctx, sb)
    clips = shots.run(ctx, sb)
    assert clips[("s03", "vertical")] is None
    assert clips[("s03", "horizontal")] is not None
    later = make_ctx(gpu=FakeGpu(tmp_path / "b"))
    assert shots.run(later, sb)[("s03", "vertical")] is not None
    assert later.providers.gpu.batches == [["s03.vertical"]]


def test_no_gpu_means_ken_burns_and_no_log_noise(make_ctx, sb, tmp_path):
    ctx = make_ctx(gpu=FakeGpu(tmp_path / "g", online=False))
    keyframes.run(ctx, sb)
    before = len(ctx.runlog.read())
    assert not any(shots.run(ctx, sb).values())
    assert len(ctx.runlog.read()) == before
    assert not any(shots.run(make_ctx(allow_gpu=False), sb).values())


def test_worker_downgrades_are_recorded(ctx, sb):
    keyframes.run(ctx, sb)
    shots.run(ctx, sb)
    assert cache.read_meta(ctx.paths.clip("s01", "vertical"))["actual"]["name"] == "s01.vertical"


def test_music_candidates_and_placeholder(ctx, sb, make_ctx):
    cue = sb["music"]["cues"][0]
    path, placeholder = music.chosen(make_ctx(allow_gpu=False), sb, cue)
    assert placeholder
    assert path.exists()
    music.run(ctx, sb)
    assert len(ctx.providers.gpu.batches[0]) == TRACKS
    assert music.chosen(ctx, sb, cue)[1] is False
    cue["caption"] += " softer"
    assert music.chosen(ctx, sb, cue)[1] is True


def test_script_repairs_an_invalid_draft(make_ctx, sb, tmp_path):
    brief = tmp_path / "brief.md"
    brief.write_text("x")
    good = json.dumps(sb)
    ctx = make_ctx(text=FakeText(["no json", json.dumps({"version": 1}), f"```json\n{good}\n```"]))
    assert json.loads(script.run(ctx, brief).read_text()) == sb
    with pytest.raises(PipelineError):
        script.run(make_ctx(text=FakeText(["no", "no", "no"])), brief)
