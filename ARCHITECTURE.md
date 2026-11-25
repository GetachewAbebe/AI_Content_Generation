# Architecture

```
storyboard.json --validate--> narration --> timeline --------------------+
                         \--> references --> keyframes --> shots (Kaggle) +--> assemble --> qc --> 2 MP4s
                          \-> music (Kaggle) -----------------------------+
```

**Contract.** `schema/storyboard.schema.json` defines it; `pipeline/validate.py` adds cross-reference checks and the consent gate. Prompts, seeds, models and mix settings live in the storyboard, not in code.

| Stage | Reads | Writes | Model |
|---|---|---|---|
| narration | `shots[].narration`, `providers.tts` | `outputs/narration/<shot>.wav` | Gemini 3.8 Flash TTS |
| keyframes | `references`, `style_block`, `shots[].keyframe` | `outputs/references/`, `outputs/keyframes/<shot>.<aspect>.png` | FLUX.2 klein 4B |
| shots | keyframes, `shots[].motion` | `outputs/clips/<shot>.<aspect>.mp4` | Wan 2.2 TI2V-5B |
| music | `music.cues` | `outputs/music/<cue>.<seed>.wav` | ACE-Step 1.5 turbo |
| assemble, qc | all of the above | `outputs/final/` | none (FFmpeg) |

**Layers.** Dependencies point one way: `cli` -> stages (`pipeline/*.py`) -> `media/`, `core/` -> provider interfaces (`providers/base.py`). Stages receive a `Context` (paths, run log, providers) and never import a concrete model. To replace a model, write one class with the same method. `--mock` and the tests swap in `providers/fake.py`; no stage knows about it.

| Package | Holds |
|---|---|
| `pipeline/*.py` | one file per stage, plus timeline, validation, QC and the CLI |
| `pipeline/core/` | config, cache, run log and retry, GPU batch handling, storyboard types |
| `pipeline/providers/` | Gemini, Cloudflare and Kaggle clients, and the fakes |
| `pipeline/media/` | FFmpeg, audio mix, picture segments, subtitles |
| `pipeline/remote/` | scripts that run on the Kaggle GPU; self-contained, not covered by tests |
| `pipeline/tools/` | smoke test, cost table, consistency scoring, ducking sweep, TTS benchmark, showcase page |

**Timing.** Measured speech plus padding sets each shot's length, rounded up to the cue's nominal beat grid and whole frames. A film outside the allowed 60-90 s is refused. The beat grid uses the requested tempo; it does not detect beats in the generated audio.

**Caching.** Each artifact has a `.meta.json` with the hash of the exact inputs that made it and the hash of the output. Stale or altered files regenerate; nothing else does. Reference images enter the hash by content, so changing the sheet invalidates dependent keyframes, and a new keyframe invalidates its clip. The 16:9 keyframe uses the 9:16 one as a reference, so one keyframe edit makes two image calls for that shot.

**Failure handling.** 429, 5xx and timeouts retry with backoff and honour `Retry-After`; other 4xx fail at once. Every attempt is logged. Files are written atomically. A Kaggle batch is named by the hash of its jobs and its state is saved after upload, push, completion and download, so a crash at any of those points resumes without submitting twice (`tests/test_kaggle.py`). Finished clips from a failed kernel are kept and only the rest are resubmitted. A batch gets three attempts. If the worker had to shorten a clip after running out of memory, the sidecar `actual` field and `runs.jsonl` say so. Without a GPU clip a shot renders as Ken Burns, and without a score a synth placeholder plays; QC fails while a placeholder remains.

**Logging.** `runs.jsonl` gets one line per model call attempt. Secrets are redacted. Mock runs write only to `build/mock/`.
