import subprocess
from pathlib import Path

import pytest

from pipeline.core.errors import MissingCredentialError, PermanentError, TransientError
from pipeline.core.runlog import RunLog
from pipeline.providers.kaggle import Kaggle, KaggleCli, parse_status

JOBS = [{"name": "s01.vertical"}]


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ('u/k has status "KernelWorkerStatus.ERROR"', "error"),
        ('u/k has status "KernelWorkerStatus.COMPLETE"', "complete"),
        ('u/k has status "KernelWorkerStatus.CANCEL_ACKNOWLEDGED"', "error"),
        ('u/k has status "KernelWorkerStatus.QUEUED"', "running"),
        ('u/k has status "complete"', "complete"),
        ("something unexpected", "running"),
    ],
)
def test_status_lines(line, expected):
    assert parse_status(line) == expected


def cli_returning(out, code=0):
    return KaggleCli(lambda *_a, **_k: subprocess.CompletedProcess([], code, out, ""))


def test_a_failed_kernel_is_a_status_not_a_cli_failure():
    assert "ERROR" in cli_returning('status "KernelWorkerStatus.ERROR"')("kernels", "status", "x")


def test_push_errors_with_exit_code_zero_are_caught():
    with pytest.raises(PermanentError):
        cli_returning("Kernel push error: quota")("kernels", "push", "-p", "x")
    with pytest.raises(TransientError):
        cli_returning("503 Server Error", 1)("kernels", "list")


class FakeKaggle:
    """Plays Kaggle's side. `statuses` is what each submitted kernel reports."""

    def __init__(self, statuses, outputs=("s01.vertical.mp4",)):
        self.statuses, self.outputs, self.calls, self.crash_on = list(statuses), outputs, [], None

    def __call__(self, *args, **_):
        verb = f"{args[0]} {args[1]}"
        if verb == self.crash_on:
            self.crash_on = None
            raise KeyboardInterrupt
        self.calls.append(verb)
        if verb == "datasets status":
            return "ready"
        if verb == "kernels status":
            return f'status "KernelWorkerStatus.{self.statuses.pop(0)}"'
        if verb == "kernels output":
            folder = Path(args[args.index("-p") + 1])
            for name in self.outputs:
                (folder / name).write_bytes(b"x")
        return ""

    def count(self, verb):
        return self.calls.count(verb)


@pytest.fixture
def lane(tmp_path, monkeypatch):
    monkeypatch.setenv("KAGGLE_USERNAME", "user")
    monkeypatch.setenv("KAGGLE_API_TOKEN", "token")

    def build(cli, **kwargs):
        return Kaggle(tmp_path / "remote", cli, sleep=lambda _: None, **kwargs), RunLog(
            tmp_path / "runs.jsonl"
        )

    return build


def test_happy_path_and_second_call_costs_nothing(lane):
    cli = FakeKaggle(["RUNNING", "COMPLETE"])
    kaggle, runlog = lane(cli)
    dest = kaggle.run_batch("wan", JOBS, {}, runlog)
    assert (dest / "s01.vertical.mp4").exists()
    before = len(cli.calls)
    assert kaggle.run_batch("wan", JOBS, {}, runlog) == dest
    assert len(cli.calls) == before


@pytest.mark.parametrize("crash", ["datasets status", "kernels push", "kernels status", "kernels output"])
def test_a_crash_at_any_step_resumes_without_paying_twice(lane, crash):
    cli = FakeKaggle(["COMPLETE", "COMPLETE"])
    cli.crash_on = crash
    kaggle, runlog = lane(cli)
    with pytest.raises(KeyboardInterrupt):
        kaggle.run_batch("wan", JOBS, {}, runlog)
    kaggle.run_batch("wan", JOBS, {}, runlog)
    assert cli.count("datasets create") == 1
    assert cli.count("kernels push") == 1


def test_failed_kernel_with_partial_output_is_kept(lane):
    kaggle, runlog = lane(FakeKaggle(["ERROR"]))
    assert list(kaggle.run_batch("wan", JOBS, {}, runlog).glob("*.mp4"))


def test_gives_up_after_three_empty_failures(lane):
    cli = FakeKaggle(["ERROR"] * 3, outputs=())
    kaggle, runlog = lane(cli)
    with pytest.raises(PermanentError, match="3 times"):
        kaggle.run_batch("wan", JOBS, {}, runlog)
    assert cli.count("kernels push") == 3


def test_long_runs_time_out_and_can_be_resumed(lane):
    kaggle, runlog = lane(FakeKaggle(["RUNNING"] * 9), max_wait_s=90, poll_s=45)
    with pytest.raises(TransientError, match="resume"):
        kaggle.run_batch("wan", JOBS, {}, runlog)


def test_unconfigured_lane_says_so(lane, monkeypatch):
    kaggle, runlog = lane(FakeKaggle([]))
    monkeypatch.delenv("KAGGLE_USERNAME")
    with pytest.raises(MissingCredentialError):
        kaggle.run_batch("wan", JOBS, {}, runlog)
