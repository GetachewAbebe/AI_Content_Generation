# Ethics

## Consent
No real person's face, likeness or voice is generated. Characters are invented and stylised (`real_person: false` in `storyboard.json`), and the narrator is a stock Gemini voice. No voice cloning is used.

The pipeline enforces this: a character marked `real_person: true` fails validation unless this file holds a matching consent record line (the words CONSENT-RECORD, a colon, and the id). See `pipeline/validate.py`.

The author states that Emama Almaz is a fictionalised composite, with no real person's likeness or cloned voice. The end card says she is fictional.

## Licences
| Component | Licence or terms | Checked |
|---|---|---|
| Wan 2.2 TI2V-5B | Apache 2.0 (model card) | 2026-11-25 |
| ACE-Step 1.5 | MIT (repository) | 2026-11-25 |
| FLUX.2 klein 4B via Cloudflare Workers AI | Apache 2.0 weights, per the challenge brief; Cloudflare service terms | author to verify |
| Gemini 3.8 Flash TTS | Gemini API terms; free-tier data use | author to verify |
| Noto Sans, Noto Sans Ethiopic | SIL Open Font License 1.1 | author to verify |

## Labelling
- End card in both exports states the film was made with AI; validation rejects a storyboard whose end card does not.
- The MP4 `comment` metadata says so too. The platform's AI disclosure is switched on when posting.
- Source files in `outputs/` keep whatever watermark their model embeds; nothing attempts to remove one.

## Private data
Family details stay out of prompts. `story/private/` is git-ignored. Gemini requests ask for `store: false`.
