# Heritage Short

A pipeline that turns `storyboard.json` into a 60-90 s narrated film in 9:16 and 16:9.

**Status:** the pipeline passes its tests and a full mock run. The storyboard is written; no real model has been called and the film is not made yet.

## Run
Needs Linux, Python 3.12 or later, `make`, and FFmpeg with libass (tested with FFmpeg 8 and Python 3.14). Python 3.12, CI and macOS are not verified yet.
```
cp .env.example .env    # add your keys
make smoke              # one real call per provider
make film               # everything, storyboard to both MP4s
```
Results: `outputs/final/film.vertical.mp4`, `film.horizontal.mp4`, `qc.json`, `timeline.json`, subtitles.

| Command | Does |
|---|---|
| `make local` | as `film`, but never submits GPU jobs |
| `make radio` | narration over music on black |
| `make mock` | whole pipeline with fake media and no keys (about 3 minutes on 8 cores) |
| `make script` | draft `storyboard.draft.json` from `story/brief.md` for a person to approve |
| `make narration`, `keyframes`, `shots`, `music` | one stage alone |
| `make consistency` | score keyframes against the reference sheet |
| `make duck-sweep`, `make tts-bench` | experiments: ducking settings, TTS in four languages |
| `make costs`, `make showcase` | update COSTS.md from the log; write a static page |
| `make validate`, `make check` | check the storyboard; lint, types and tests |

## What it costs
Nothing on the free tiers. Measured latency, GPU minutes and list-price equivalents: [COSTS.md](COSTS.md).

## Documents
[DESIGN](DESIGN.md), [ARCHITECTURE](ARCHITECTURE.md), [EXPERIMENTS](EXPERIMENTS.md), [FAILURES](FAILURES.md), [COSTS](COSTS.md), [ETHICS](ETHICS.md). Progress against the challenge: [CHECKLIST](CHECKLIST.md).

Edit one shot in `storyboard.json` and run `make film` again: only that shot regenerates. See [ARCHITECTURE.md](ARCHITECTURE.md).
