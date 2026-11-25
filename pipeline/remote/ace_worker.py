"""ACE-Step 1.5 turbo (DiT only, no LM planner) on one Kaggle GPU. Saves every candidate as it finishes."""

import json
import os
import shutil
import subprocess
import sys
import time
import traceback

SRC, DST = sys.argv[1], sys.argv[2]
REPO = "/tmp/ACE-Step-1.5"


def log(**k):
    with open(f"{DST}/gpu_runs.jsonl", "a") as f:
        f.write(json.dumps(k) + "\n")


def parent():
    t = time.time()
    subprocess.run(
        ["git", "clone", "--depth", "1", "https://github.com/ACE-Step/ACE-Step-1.5.git", REPO], check=True
    )
    rev = subprocess.run(
        ["git", "-C", REPO, "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "uv"], check=True)
    subprocess.run([sys.executable, "-m", "uv", "sync", "--python", "3.11"], cwd=REPO, check=True)
    log(event="install", seconds=round(time.time() - t, 1), ok=True, repo_commit=rev)
    sys.exit(
        subprocess.run(
            [sys.executable, "-m", "uv", "run", "python", __file__, SRC, DST, "gen"],
            cwd=REPO,
            check=False,
            env={**os.environ, "CUDA_VISIBLE_DEVICES": "0", "PYTHONPATH": REPO},
        ).returncode
    )


def gen():
    import dataclasses

    from acestep.handler import AceStepHandler
    from acestep.inference import GenerationConfig, GenerationParams, generate_music
    from acestep.llm_inference import LLMHandler

    with open(f"{SRC}/job.json") as handle:
        jobs = json.load(handle)["jobs"]
    t = time.time()
    dit, llm = AceStepHandler(), LLMHandler()
    log(
        event="load",
        result=str(dit.initialize_service(project_root=REPO, config_path=jobs[0]["model"], device="cuda"))[
            :300
        ],
        seconds=round(time.time() - t, 1),
        ok=True,
    )

    def make(cls, d):  # the API moves fast: pass only fields this version knows
        names = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in names})

    for j in jobs:
        t, ok, err = time.time(), False, None
        try:
            p = make(
                GenerationParams,
                dict(
                    caption=j["caption"],
                    lyrics="[Instrumental]",
                    instrumental=True,
                    bpm=j["bpm"],
                    keyscale=j["keyscale"],
                    duration=j["duration_s"],
                    inference_steps=j["steps"],
                    shift=3.0,
                    seed=j["seed"],
                    thinking=False,
                    use_cot_metas=False,
                    use_cot_caption=False,
                    use_cot_language=False,
                ),
            )
            c = make(
                GenerationConfig,
                dict(batch_size=1, use_random_seed=False, seeds=[j["seed"]], audio_format="wav"),
            )
            r = generate_music(dit, llm, p, c, save_dir=f"/tmp/ace/{j['name']}")
            if not r.success:
                raise RuntimeError(str(r.error))
            shutil.copy(r.audios[0]["path"], f"{DST}/{j['name']}.wav")
            ok = True
        except Exception as e:
            err = f"{type(e).__name__}: {str(e)[:300]}"
            traceback.print_exc()
        log(
            event="track",
            name=j["name"],
            seconds=round(time.time() - t, 1),
            ok=ok,
            error=err,
            seed=j["seed"],
            gpu="T4",
        )


(gen if len(sys.argv) > 3 else parent)()
