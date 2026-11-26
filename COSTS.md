# Costs

Regenerate the table with `make costs`. Real spend is zero on the free tiers; list price is what the same calls would cost.

<!-- generated:start -->
| Stage | Model | Attempts | OK | Retried | Failed | Median latency (s) | GPU min | List price (USD) | Paid (USD) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| consistency | gemini-3.8-flash | 5 | 0 | 4 | 1 | - | 0.0 | - | 0.00 |
| keyframe | @cf/black-forest-labs/flux-2-klein-4b | 40 | 40 | 0 | 0 | 7.4 | 0.0 | 0.0748 | 0.00 |
| music | acestep-v15-turbo | 6 | 6 | 0 | 0 | 5.1 | 0.6 | - | 0.00 |
| music_install | acestep-v15-turbo | 1 | 1 | 0 | 0 | 211.4 | 3.5 | - | 0.00 |
| music_load | acestep-v15-turbo | 1 | 1 | 0 | 0 | 57.9 | 1.0 | - | 0.00 |
| narration | gemini-3.8-flash-tts | 11 | 9 | 1 | 1 | 4.0 | 0.0 | 0.0150 | 0.00 |
| reference | @cf/black-forest-labs/flux-2-klein-4b | 6 | 6 | 0 | 0 | 8.3 | 0.0 | 0.0071 | 0.00 |
| remote | kaggle-api | 29 | 25 | 3 | 1 | 3.5 | 0.0 | - | 0.00 |
| smoke | @cf/black-forest-labs/flux-2-klein-4b | 4 | 2 | 0 | 2 | 5.5 | 0.0 | 0.0021 | 0.00 |
| smoke | gemini-3.8-flash | 5 | 0 | 2 | 3 | - | 0.0 | - | 0.00 |
| smoke | gemini-3.8-flash-tts | 3 | 2 | 0 | 1 | 3.8 | 0.0 | 0.0020 | 0.00 |
<!-- generated:end -->

## Limits and list prices found in the documentation (25 November 2026)
| Service | Free allowance | List price |
|---|---|---|
| Gemini 3.8 Flash TTS | free tier; daily limit to be noted from real use | $0.50 / 1M text in, $9.00 / 1M audio out, 25 audio tokens per second |
| Gemini 3.8 Flash | free tier | $0.75 / 1M in, $3.75 / 1M out |
| FLUX.2 klein 4B on Cloudflare | 10,000 neurons a day, reset 00:00 UTC (03:00 EAT) | 26.05 neurons per output 512 px tile, 5.37 per input tile, $0.011 per 1,000 |
| Kaggle T4 x2 | about 30 GPU hours a week (challenge brief) | no list price; compare with a rented T4 |

One 720x1280 keyframe is six tiles, about 156 neurons plus references. A full set of 24 is about 4,000 neurons, so two or three complete passes fit in a day. This is an estimate until the smoke test runs.

## Frontier comparison
No frontier access has been opened for this project so far.
