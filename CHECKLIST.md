# Challenge checklist

Status: **built** = code exists and is tested, **ready** = waiting only on an input, **open** = not done. Owner: A = author, P = pipeline.

## Deliverables
| Requirement | Status | Owner | Evidence or what is missing |
|---|---|---|---|
| storyboard.json contract, JSON Schema, validated every run | built | A+P | `storyboard.json`, 10 shots, validated |
| 8-12 shots, each with a stated reason | built (enforced) | P | `reason` is required by the schema |
| One script per stage: script, keyframes, shots, music, narration, assemble | built | P | `pipeline/` |
| Caching: only what changed regenerates | built | P | `tests/test_stages.py` |
| Retries, resume, fallbacks | built | P | `tests/test_core.py`, `test_kaggle.py` |
| runs.jsonl: model, parameters, seed, latency, cost | built, **open** (no real calls yet) | P | `core/runlog.py` |
| One command from a clean clone | built in mock mode; **open** for the real film | P | `make film` |
| No secrets committed | built | P | `.gitignore`, redaction and repository tests |
| outputs/ kept for inspection | ready | P | `.gitignore` drops only rebuildable files |
| README, ARCHITECTURE | built | P | to be updated with real results |

## Phase 1
| Requirement | Status | Owner |
|---|---|---|
| Accounts and keys | **open** (Kaggle only) | A |
| Smoke test per provider, logged | ready (`make smoke`) | A runs it |
| Story, audience and intent in DESIGN.md before generating | done; why it matters to the family **open** | A |
| Consent | done: fictional character, no real likeness or voice | A |
| Amharic narration and radio cut | ready (`make radio`) | P |
| User test 1, at least three people | **open** | A |

## Phase 2
| Requirement | Status | Owner |
|---|---|---|
| Reference sheet, then conditioned keyframes | ready | P |
| Character consistency check | ready (`make consistency`) plus the author's eye | A+P |
| Wan 2.2 clips on Kaggle | written, never run on a GPU | P |
| Three ACE-Step candidates, choice explained | written, never run on a GPU; choosing needs the author's ears | A+P |
| At least ten experiments with hypotheses | **open**, 0 of 10 | A+P |
| FAILURES.md | 7 entries so far | P |

## Phase 3
| Requirement | Status | Owner |
|---|---|---|
| Both aspect ratios, 60-90 s, ducking, loudness, burned-in subtitles, AI end card | built, checked by `qc.py` | P |
| Cut to the music | partly: cuts snap to the requested tempo, not to detected beats | P |
| User test 2, at least three people | **open** | A |
| COSTS.md with measured values and list prices | ready (`make costs`) | P |
| Frontier comparison | not possible unless access opens | - |
| ETHICS.md | partly: some licences to verify | A+P |
| Report (PDF or link) | **open**, outline in `docs/REPORT_OUTLINE.md` | A |
| Walkthrough, at most 5 minutes | **open**, plan in `docs/WALKTHROUGH.md` | A |
| Public post, AI label on | **open**, prompts in `docs/POST_PROMPTS.md` | A |
| Ceiling: TTS in four languages | ready (`make tts-bench`); sentences need native-speaker checks | A+P |
| Ceiling: a tool for others | built: `heritage` command and provider interfaces | P |
| Two submissions by Thu 26 Nov, 23:59 EAT | **open** | A |
