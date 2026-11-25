# Costs

Regenerate the table with `make costs`. Real spend is zero on the free tiers; list price is what the same calls would cost.

<!-- generated:start -->
No real model calls yet.
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
