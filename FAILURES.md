# Failure journal

## F1. The TTS request shape everyone remembers is gone (25 Nov)
The documentation URL redirects to aistudio.google.com, and its TTS examples use the Interactions API (`/v1beta/interactions`) instead of `generateContent` with `voiceConfig`. No seed is documented. **Response:** client written for the new shape; `take` in the storyboard stands in for a seed, so a re-performance is an explicit, logged change. Not yet confirmed by a live call.

## F2. FLUX.2 klein request fields are undocumented (25 Nov)
The published schema has an untyped multipart body. Search confirmed `input_image_0..3` and a sub-512 px reference limit (stated for the 9B model). `seed`, `width` and `height` are unconfirmed for 4B. **Response:** references are shrunk to 496 px, and the smoke test checks the returned size.

## F3. Afaan Oromo is not on the TTS language list (25 Nov)
Amharic, Tigrinya and Somali are listed for `gemini-3.8-flash-tts`; Oromo is not.

## F4. Suggested ducking removed the music (25 Nov, synthetic audio)
Threshold 0.02, ratio 6, 300/1500 ms gave -18.1 dB under a continuous test tone at -16 LUFS. Synthetic only; to be repeated on real narration as an experiment.

## F5. Our own bug: a failed GPU job would have been polled for six hours (25 Nov)
Found in code review before any GPU run. The CLI wrapper treated the word "error" in the first output line as a command failure, and Kaggle reports a failed kernel as `KernelWorkerStatus.ERROR`. Reproduced by feeding that line to the wrapper. **Fix:** the status is parsed, and the soft-error check applies only to `create` and `push`. Test: `test_a_failed_kernel_is_a_status_not_a_cli_failure`.

## F6. Our own bug: resume failed if the crash came between upload and launch (25 Nov)
State was saved only after both steps, so a rerun would upload the same dataset name again. **Fix:** state is saved after each step. Test: a crash injected at four different steps.

## F7. Our own bug: a shortened clip was recorded as full length (25 Nov)
After an out-of-memory error the worker retries with fewer frames, and the cache did not say so. **Fix:** the sidecar and the log keep what was really made.

## F8. Our own bug: the installed `heritage` command could not find its schema (25 Nov)
The checklist called the command built, but it had only been run from the checkout. Installed into a separate environment it raised `FileNotFoundError` for the schema. **Fix:** the project folder comes from `HERITAGE_HOME`, the checkout, or the current folder. Checked from an installed copy in two folders. The Python 3.12 container run that prompted this was stopped before its tests ran, so 3.12 is still unverified.
