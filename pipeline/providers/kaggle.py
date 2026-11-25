"""GPU lane on Kaggle (T4 x2): upload, push, poll, download, resume.

A batch is named by the hash of its jobs, and progress is saved after every step. If this process dies,
the next run continues the same batch instead of spending GPU quota twice.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..core.cache import digest, file_digest
from ..core.config import redact, require
from ..core.errors import MissingCredentialError, PermanentError, TransientError
from ..core.log import log
from ..core.runlog import CallInfo, ModelResult, RunLog

WORKERS = Path(__file__).resolve().parents[1] / "remote"
ACCELERATOR = "NvidiaTeslaT4"
MAX_BATCH_ATTEMPTS = 3
TRANSIENT_MARKS = ("429", "500", "502", "503", "504", "timed out", "Connection")
DONE, FAILED, RUNNING = "complete", "error", "running"


def parse_status(text: str) -> str:
    """Kaggle prints: owner/slug has status "KernelWorkerStatus.COMPLETE"."""
    match = re.search(r'status "?(?:KernelWorkerStatus\.)?(\w+)', text, re.IGNORECASE)
    word = match.group(1).lower() if match else ""
    if word.startswith("complete"):
        return DONE
    if word.startswith(("error", "cancel", "fail")):
        return FAILED
    return RUNNING


class KaggleCli:
    def __init__(self, runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run) -> None:
        self._run = runner
        beside = Path(sys.executable).with_name("kaggle")
        self._exe = str(beside) if beside.exists() else "kaggle"

    def __call__(self, *args: str, timeout: float = 900) -> str:
        try:
            result = self._run(
                [self._exe, *args], capture_output=True, text=True, timeout=timeout, check=False
            )
        except subprocess.TimeoutExpired as err:
            raise TransientError(f"kaggle {args[0]} {args[1]} timed out") from err
        output = redact(result.stdout + result.stderr)
        # `create` and `push` report some failures with exit code 0; `status` legitimately prints "ERROR".
        soft_failure = args[1] in ("create", "push") and "error" in output.lower()
        if result.returncode or soft_failure:
            kind = TransientError if any(mark in output for mark in TRANSIENT_MARKS) else PermanentError
            raise kind(f"kaggle {args[0]} {args[1]}: {output[-500:]}")
        return output


class Kaggle:
    name = "kaggle"

    def __init__(
        self,
        state_dir: Path,
        cli: Callable[..., str] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_wait_s: float = 4 * 3600,
        poll_s: float = 45,
    ) -> None:
        self.state_dir, self.cli, self.sleep = state_dir, cli or KaggleCli(), sleep
        self.max_wait_s, self.poll_s = max_wait_s, poll_s

    def available(self) -> bool:
        home = Path.home() / ".kaggle"
        token = os.environ.get("KAGGLE_API_TOKEN") or any(
            (home / name).exists() for name in ("kaggle.json", "access_token")
        )
        return bool(os.environ.get("KAGGLE_USERNAME") and token)

    def run_batch(
        self, kind: str, jobs: list[dict[str, Any]], files: dict[str, Path], runlog: RunLog
    ) -> Path:
        if not self.available():
            raise MissingCredentialError("Kaggle is not configured (KAGGLE_USERNAME plus a token)")
        worker = WORKERS / f"{kind}_worker.py"
        base = digest({"kind": kind, "jobs": jobs, "worker": file_digest(worker)})[:10]
        for attempt in range(1, MAX_BATCH_ATTEMPTS + 1):
            batch = Batch(self, kind, f"{base}-{attempt}", jobs, files, runlog)
            if batch.state.get("status") == FAILED:
                continue
            if batch.finish() == DONE or batch.has_output():
                return batch.dest
            log.info("kaggle: batch %s failed with no output; see %s", batch.id, batch.dest)
        raise PermanentError(f"Kaggle {kind} batch failed {MAX_BATCH_ATTEMPTS} times")


class Batch:
    """One submission. `state` is persisted after each step so every step is resumable."""

    def __init__(
        self,
        lane: Kaggle,
        kind: str,
        batch_id: str,
        jobs: list[dict[str, Any]],
        files: dict[str, Path],
        runlog: RunLog,
    ) -> None:
        self.lane, self.kind, self.id, self.jobs, self.files, self.runlog = (
            lane,
            kind,
            batch_id,
            jobs,
            files,
            runlog,
        )
        user = require("KAGGLE_USERNAME")
        self.dataset = f"{user}/heritage-in-{batch_id}"
        self.kernel = f"{user}/heritage-{kind}-{batch_id}"
        self.dest = lane.state_dir / f"{kind}-{batch_id}"
        self._file = lane.state_dir / f"{kind}-{batch_id}.json"
        self.state: dict[str, Any] = json.loads(self._file.read_text()) if self._file.exists() else {}

    def _save(self, **updates: Any) -> None:
        self.state.update(updates)
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._file.write_text(json.dumps(self.state))

    def _logged(self, *args: str) -> None:
        info = CallInfo("remote", self.id, "kaggle", "kaggle-api", {"cmd": f"{args[0]} {args[1]}"})
        self.runlog.call(info, lambda: ModelResult(self.lane.cli(*args).encode()), sleep=self.lane.sleep)

    def has_output(self) -> bool:
        return any(self.dest.glob("*.mp4")) or any(self.dest.glob("*.wav"))

    def finish(self) -> str:
        if not self.state.get("dataset"):
            log.info("kaggle: uploading %d %s job(s) as batch %s", len(self.jobs), self.kind, self.id)
            self._upload()
            self._save(dataset=self.dataset)
        if not self.state.get("kernel"):
            self._wait_for_dataset()
            self._push()
            self._save(kernel=self.kernel, status=RUNNING)
        if self.state["status"] == RUNNING:
            log.info("kaggle: waiting on %s", self.kernel)
            self._save(status=self._poll())
        if not self.dest.exists():
            self.dest.mkdir(parents=True)
            self._logged("kernels", "output", self.kernel, "-p", str(self.dest), "-o")
        return self.state["status"]

    def _upload(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, source in self.files.items():
                shutil.copy(source, root / name)
            shutil.copy(WORKERS / f"{self.kind}_worker.py", root / "worker.py")
            (root / "job.json").write_text(
                json.dumps({"batch": self.id, "jobs": self.jobs}, ensure_ascii=False)
            )
            meta = {"title": self.dataset.split("/")[1], "id": self.dataset, "licenses": [{"name": "other"}]}
            (root / "dataset-metadata.json").write_text(json.dumps(meta))
            self._logged("datasets", "create", "-p", folder)

    def _wait_for_dataset(self, tries: int = 40) -> None:
        for _ in range(tries):
            try:
                if "ready" in self.lane.cli("datasets", "status", self.dataset).lower():
                    return
            except (PermanentError, TransientError) as err:  # 403/404 until Kaggle indexes it
                log.info("kaggle: dataset not visible yet (%s)", str(err)[:80])
            self.lane.sleep(15)
        raise TransientError("Kaggle dataset never became ready; rerun to resume")

    def _push(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            launcher = (WORKERS / "launch.py").read_text().replace("__BATCH__", self.id)
            (root / "kernel.py").write_text(launcher)
            meta = {
                "id": self.kernel,
                "title": self.kernel.split("/")[1],
                "code_file": "kernel.py",
                "language": "python",
                "kernel_type": "script",
                "is_private": "true",
                "enable_gpu": "true",
                "enable_internet": "true",
                "machine_shape": ACCELERATOR,
                "dataset_sources": [self.dataset],
                "competition_sources": [],
                "kernel_sources": [],
                "model_sources": [],
            }
            (root / "kernel-metadata.json").write_text(json.dumps(meta))
            self._logged("kernels", "push", "-p", folder, "--accelerator", ACCELERATOR)

    def _poll(self) -> str:
        waited = 0.0
        while waited < self.lane.max_wait_s:
            try:
                status = parse_status(self.lane.cli("kernels", "status", self.kernel))
            except (PermanentError, TransientError) as err:
                log.info("kaggle: status check failed, polling again (%s)", str(err)[:80])
                status = RUNNING
            if status != RUNNING:
                return status
            self.lane.sleep(self.lane.poll_s)
            waited += self.lane.poll_s
        raise TransientError(
            f"{self.kernel} still running after {self.lane.max_wait_s:.0f}s; rerun to resume"
        )
