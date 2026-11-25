"""Writes storyboard.mock.json: placeholder content for tests. It is not the film."""

import json
import pathlib

moves = ["push_in", "pan_left", "pull_out", "pan_right", "tilt_up", "tilt_down"]
sb = {
    "version": 1,
    "title": {"native": "የሙከራ ርዕስ", "en": "Test title"},
    "language": {"code": "am", "name": "Amharic"},
    "logline": "Plumbing test.",
    "audience": "Developers.",
    "intent": "Prove the stages connect.",
    "duration_s": {"min": 60, "max": 90},
    "style_block": "Plain test style.",
    "characters": [{"id": "hero", "description": "A test figure.", "real_person": False}],
    "references": [
        {
            "id": "hero_sheet",
            "kind": "character",
            "prompt": "Character sheet.",
            "seed": 1,
            "characters": ["hero"],
        }
    ],
    "providers": {
        "tts": {"model": "gemini-3.8-flash-tts", "voice": "Sulafat", "style": "calm"},
        "image": {"model": "@cf/black-forest-labs/flux-2-klein-4b", "steps": 4},
        "video": {
            "model": "Wan-AI/Wan2.2-TI2V-5B-Diffusers",
            "long_side": 416,
            "short_side": 224,
            "num_frames": 41,
            "fps": 24,
            "steps": 30,
            "guidance": 5.0,
            "flow_shift": 3.0,
        },
        "music": {"model": "acestep-v15-turbo", "steps": 8},
    },
    "shots": [
        {
            "id": f"s{n:02}",
            "reason": f"Exercises shot {n}.",
            "shot_size": "wide",
            "min_duration_s": 6.5,
            "keyframe": {
                "prompt": f"Test frame {n}.",
                "seed": n,
                "references": ["hero_sheet"],
                "characters": ["hero"],
            },
            "motion": {
                "backend": "wan" if n % 2 else "kenburns",
                "prompt": "Gentle wind.",
                "seed": n,
                "kenburns": moves[n % 6],
            },
            "narration": {
                "text": "ይህ የሙከራ መስመር ነው። " * 3 + str(n),
                "subtitle_en": f"This is test line {n}, which wraps onto two lines.",
            },
        }
        for n in range(1, 10)
    ],
    "music": {
        "cues": [
            {
                "id": "open",
                "start_shot": "s01",
                "purpose": "Opening.",
                "caption": "instrumental test",
                "bpm": 66,
                "keyscale": "D Major",
                "duration_s": 12,
                "seeds": [1, 2, 3],
                "chosen_seed": 1,
            },
            {
                "id": "close",
                "start_shot": "s06",
                "purpose": "Closing.",
                "caption": "instrumental test",
                "bpm": 66,
                "keyscale": "D Major",
                "duration_s": 12,
                "seeds": [4, 5],
                "chosen_seed": 4,
            },
        ]
    },
    "mix": {
        "target_lufs": -14,
        "true_peak_db": -1,
        "narration_lufs": -16,
        "music_lufs": -24,
        "duck": {"threshold": 0.02, "ratio": 6, "attack_ms": 300, "release_ms": 1500},
        "head_pad_s": 0.5,
        "tail_pad_s": 0.7,
        "snap_to_beat": True,
    },
    "end_card": {
        "duration_s": 3,
        "lines": [
            "የሙከራ ርዕስ",
            "This film was made with AI.",
            "Pictures, motion, music and voice are generated.",
        ],
    },
}
pathlib.Path(__file__).with_name("storyboard.mock.json").write_text(
    json.dumps(sb, indent=1, ensure_ascii=False)
)
