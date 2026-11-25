PY := .venv/bin/python
HERITAGE := $(PY) -m pipeline
.PHONY: setup film local radio validate script narration keyframes shots music smoke consistency duck-sweep tts-bench costs showcase mock test lint check

setup: .venv/.ok
.venv/.ok: requirements.txt
	python3 -m venv .venv
	.venv/bin/pip install -q -r requirements.txt
	@touch $@

film: setup  ## whole pipeline, storyboard to both MP4s
	$(HERITAGE) film
local: setup  ## as film, but never submits GPU jobs
	$(HERITAGE) film --no-gpu
radio validate script narration keyframes shots music smoke consistency duck-sweep tts-bench costs showcase: setup
	$(HERITAGE) $@
mock: setup  ## whole pipeline with fake providers; no keys, writes only to build/mock
	$(HERITAGE) film --mock --storyboard tests/fixtures/storyboard.mock.json
test: setup
	$(PY) -m pytest -q
lint: setup
	.venv/bin/ruff check pipeline tests && .venv/bin/ruff format --check pipeline tests && .venv/bin/mypy pipeline
check: lint test
