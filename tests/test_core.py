import subprocess

import pytest

from pipeline.core import cache
from pipeline.core.config import ROOT, find_root, load_env
from pipeline.core.errors import PermanentError, TransientError
from pipeline.core.runlog import CallInfo, ModelResult, RunLog

INFO = CallInfo("stage", "thing", "provider", "model")


def test_cache_tracks_inputs_and_tampering(tmp_path):
    path = tmp_path / "a.bin"
    cache.store(path, b"one", {"x": 1})
    assert cache.is_fresh(path, {"x": 1})
    assert not cache.is_fresh(path, {"x": 2})
    path.write_bytes(b"changed")
    assert not cache.is_fresh(path, {"x": 1})


def test_atomic_write_leaves_nothing_behind_on_failure(tmp_path):
    target = tmp_path / "out.bin"
    with pytest.raises(RuntimeError), cache.atomic(target) as temp:
        temp.write_bytes(b"half")
        raise RuntimeError
    assert list(tmp_path.iterdir()) == []


def flaky(failures, error):
    state = {"n": 0}

    def func():
        state["n"] += 1
        if state["n"] <= failures:
            raise error
        return ModelResult(b"ok")

    return func


def test_transient_errors_retry_and_every_attempt_is_logged(tmp_path):
    runlog, waits = RunLog(tmp_path / "runs.jsonl"), []
    result = runlog.call(INFO, flaky(2, TransientError("HTTP 429", retry_after=7)), sleep=waits.append)
    assert result.data == b"ok"
    assert [x["status"] for x in runlog.read()] == ["retry", "retry", "ok"]
    assert waits == [7, 7]


def test_gives_up_after_the_last_attempt(tmp_path):
    runlog = RunLog(tmp_path / "runs.jsonl")
    with pytest.raises(TransientError):
        runlog.call(INFO, flaky(9, TransientError("HTTP 503")), attempts=3, sleep=lambda _: None)
    assert [x["status"] for x in runlog.read()] == ["retry", "retry", "error"]


def test_daily_quota_is_not_waited_out(tmp_path):
    with pytest.raises(TransientError):
        RunLog(tmp_path / "r").call(
            INFO, flaky(1, TransientError("quota", retry_after=9999)), sleep=lambda _: None
        )


def test_permanent_errors_are_not_retried(tmp_path):
    runlog = RunLog(tmp_path / "runs.jsonl")
    with pytest.raises(PermanentError):
        runlog.call(INFO, flaky(1, PermanentError("HTTP 400")))
    assert len(runlog.read()) == 1


def test_secrets_never_reach_the_log(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "sk-very-secret")
    runlog = RunLog(tmp_path / "runs.jsonl")
    with pytest.raises(PermanentError):
        runlog.call(INFO, flaky(1, PermanentError("bad key sk-very-secret")))
    assert "sk-very-secret" not in runlog.path.read_text()


def test_env_file_does_not_override_the_shell(tmp_path, monkeypatch):
    monkeypatch.setenv("KAGGLE_USERNAME", "shell")
    env = tmp_path / ".env"
    env.write_text("# note\nKAGGLE_USERNAME=file\nHERITAGE_TEST='quoted'\n")
    monkeypatch.delenv("HERITAGE_TEST", raising=False)
    load_env(env)
    import os

    assert os.environ["KAGGLE_USERNAME"] == "shell"
    assert os.environ.pop("HERITAGE_TEST") == "quoted"


def test_no_secret_files_in_the_repository():
    command = ["git", "ls-files", "-co", "--exclude-standard"]
    names = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    assert not [n for n in names if n.split("/")[-1] in (".env", "kaggle.json", "access_token")]


def test_root_can_be_set_for_an_installed_command(tmp_path, monkeypatch):
    monkeypatch.setenv("HERITAGE_HOME", str(tmp_path))
    assert find_root() == tmp_path
    monkeypatch.delenv("HERITAGE_HOME")
    assert find_root() == ROOT
