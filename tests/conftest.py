import json
from pathlib import Path

import pytest

from pipeline.core.config import Paths
from pipeline.core.context import Context
from pipeline.core.runlog import RunLog
from pipeline.providers.base import Providers
from pipeline.providers.fake import FakeGpu, FakeImage, FakeSpeech, FakeText

FIXTURE = Path(__file__).parent / "fixtures" / "storyboard.mock.json"


@pytest.fixture
def sb():
    return json.loads(FIXTURE.read_text())


@pytest.fixture
def make_ctx(tmp_path):
    def build(*, gpu=None, text=None, allow_gpu=True):
        paths = Paths(tmp_path)
        gpu = gpu or FakeGpu(tmp_path / "gpu")
        return Context(
            paths,
            RunLog(paths.runs),
            Providers(FakeSpeech(), FakeImage(), text or FakeText(), gpu),
            allow_gpu,
        )

    return build


@pytest.fixture
def ctx(make_ctx):
    return make_ctx()
