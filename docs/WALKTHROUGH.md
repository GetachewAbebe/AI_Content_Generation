# Walkthrough plan (5 minutes at most, recorded by the author)

| Time | Show | Say |
|---|---|---|
| 0:00 | 10 s of the film | whose story it is, who it is for |
| 0:20 | ARCHITECTURE.md diagram | one contract, five stages, why narration sets the timing |
| 1:20 | one shot in storyboard.json, its `.meta.json`, its line in runs.jsonl | how an input hash decides what regenerates |
| 2:10 | one hard decision, with its EXPERIMENTS.md entry | what you tried, what you measured, what you gave up |
| 3:10 | `wc -l runs.jsonl`; edit one narration line; `make local`; `wc -l` again; `tail -1 runs.jsonl` | exactly one new model call, only that shot changed |
| 4:20 | the changed moment in the film | one thing you would build next |

Use a narration line for the live part: it is one call. A keyframe prompt is two calls, one per aspect ratio. Rehearse once, then `git checkout storyboard.json` and `make local`.
