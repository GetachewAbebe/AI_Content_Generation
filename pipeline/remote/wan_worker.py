"""Wan 2.2 TI2V-5B image-to-video on Kaggle T4 x2. Saves every clip as soon as it finishes.

parent -> `encode` once on GPU 0 (frees the 11 GB text encoder when the process exits)
       -> one `gen` process per GPU, each holding the 5B transformer in fp16
"""

import fcntl
import json
import os
import subprocess
import sys
import time
import traceback

SRC, DST = sys.argv[1], sys.argv[2]
MODE = sys.argv[3] if len(sys.argv) > 3 else "parent"
with open(f"{SRC}/job.json") as handle:
    JOBS = json.load(handle)["jobs"]
EMB = "/tmp/emb.pt"


def log(**k):
    with open(f"{DST}/gpu_runs.jsonl", "a") as f:
        f.write(json.dumps(k) + "\n")


def parent():
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-q",
            "diffusers>=0.35",
            "transformers>=4.49,<5",
            "accelerate",
            "ftfy",
            "imageio",
            "imageio-ffmpeg",
        ],
        check=True,
    )
    # Download once, before two processes could race for it.
    subprocess.run(
        [
            sys.executable,
            "-c",
            "from huggingface_hub import snapshot_download as s; "
            f"s('{JOBS[0]['model']}', allow_patterns=['*.json','*.safetensors','*.model','*.txt'])",
        ],
        check=True,
    )
    me = [sys.executable, __file__, SRC, DST]
    subprocess.run(me + ["encode"], check=True, env={**os.environ, "CUDA_VISIBLE_DEVICES": "0"})
    import torch

    n = max(1, torch.cuda.device_count())
    ps = [
        subprocess.Popen(
            me + ["gen", str(g), str(n)],
            env={
                **os.environ,
                "CUDA_VISIBLE_DEVICES": str(g),
                "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
            },
        )
        for g in range(n)
    ]
    sys.exit(max(p.wait() for p in ps))


def encode():
    import torch
    from diffusers import WanPipeline

    t = time.time()
    pipe = WanPipeline.from_pretrained(
        JOBS[0]["model"], transformer=None, vae=None, torch_dtype=torch.bfloat16
    )
    pipe.text_encoder.to("cuda")
    out = {}
    for s in {j["prompt"] for j in JOBS} | {j["negative_prompt"] for j in JOBS}:
        e, _ = pipe.encode_prompt(
            s, do_classifier_free_guidance=False, max_sequence_length=512, device="cuda"
        )
        out[s] = e.float().cpu()
    torch.save(out, EMB)
    log(event="encode", n=len(out), seconds=round(time.time() - t, 1), ok=True)


def gen(g, n):
    import numpy as np
    import torch
    from diffusers import AutoencoderKLWan, UniPCMultistepScheduler, WanImageToVideoPipeline
    from diffusers.utils import export_to_video
    from PIL import Image, ImageOps

    mine = JOBS[g::n]
    if not mine:
        return
    m, t0 = mine[0]["model"], time.time()
    with open("/tmp/load.lock", "w") as lk:  # load one at a time: two at once exhausts 30 GB RAM
        fcntl.flock(lk, fcntl.LOCK_EX)
        vae = AutoencoderKLWan.from_pretrained(m, subfolder="vae", torch_dtype=torch.float32)
        pipe = WanImageToVideoPipeline.from_pretrained(
            m,
            vae=vae,
            text_encoder=None,
            tokenizer=None,
            image_encoder=None,
            image_processor=None,
            torch_dtype=torch.float16,
        ).to("cuda")
    pipe.vae.to(torch.float32)
    pipe.vae.enable_tiling()
    emb = torch.load(EMB)
    log(event="load", gpu=g, seconds=round(time.time() - t0, 1), ok=True)
    for j in mine:
        for attempt in (1, 2):
            t, ok, err, peak = time.time(), False, None, None
            steps = j["steps"]
            # second attempt after OOM uses fewer frames; 4k+1 rule
            frames = j["num_frames"] if attempt == 1 else max(17, (j["num_frames"] * 2 // 3 - 1) // 4 * 4 + 1)
            try:
                torch.cuda.reset_peak_memory_stats()
                pipe.scheduler = UniPCMultistepScheduler.from_config(
                    pipe.scheduler.config, flow_shift=j["flow_shift"]
                )
                im = ImageOps.fit(
                    Image.open(f"{SRC}/{j['image']}").convert("RGB"), (j["width"], j["height"]), Image.LANCZOS
                )
                v = pipe(
                    image=im,
                    prompt_embeds=emb[j["prompt"]].to("cuda", torch.float16),
                    negative_prompt_embeds=emb[j["negative_prompt"]].to("cuda", torch.float16),
                    height=j["height"],
                    width=j["width"],
                    num_frames=frames,
                    num_inference_steps=steps,
                    guidance_scale=j["guidance"],
                    generator=torch.Generator("cuda").manual_seed(j["seed"]),
                ).frames[0]
                a = np.asarray(v)
                peak = round(torch.cuda.max_memory_allocated() / 2**30, 2)
                if not np.isfinite(a).all() or a[len(a) // 2].std() < 0.01:
                    raise RuntimeError("degenerate frames (NaN or flat): fp16 overflow suspected")
                export_to_video(v, f"{DST}/{j['name']}.tmp.mp4", fps=j["fps"])
                os.replace(f"{DST}/{j['name']}.tmp.mp4", f"{DST}/{j['name']}.mp4")
                ok = True
            except Exception as e:
                err = f"{type(e).__name__}: {str(e)[:300]}"
                traceback.print_exc()
                torch.cuda.empty_cache()
            log(
                event="clip",
                name=j["name"],
                gpu=torch.cuda.get_device_name(0),
                seconds=round(time.time() - t, 1),
                ok=ok,
                error=err,
                attempt=attempt,
                peak_vram_gb=peak,
                frames=frames,
                steps=steps,
                size=[j["width"], j["height"]],
                seed=j["seed"],
            )
            if ok:
                break


{"parent": parent, "encode": encode}.get(MODE, lambda: gen(int(sys.argv[4]), int(sys.argv[5])))()
