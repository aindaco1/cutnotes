# Public-domain audio review

September 22, 2026. The user asked to assess cleaner recordings, review the raw
transcript and Apple output, and manually accept those results before releasing
1.0.5. They requested public-domain human speech about screenplays or film cuts.

## Sources and scope

The [source manifest](../tests/fixtures/public-audio.json) records exact download
URLs, source SHA-256 hashes, excerpt boundaries and derived WAV hashes.

| Control | Source interval | What it exercises |
| --- | --- | --- |
| Film critique: pacing and visual rhythm | 4:50.65–7:06.10 | A single narrator discussing visual strengths, pacing, romance and transitions in *The Spoilers* |
| Script planning and visual explanation | 4:11.05–5:32.30 | A production conversation about clear visual explanation, audience level and script purpose |
| Editing flow and purposeful color | 14:05.70–15:35.85 | Editing continuity, sound and when color contributes to the subject |

The first excerpt is Availle's LibriVox reading of chapter II of Vachel Lindsay's
[*The Art of the Moving Picture*](https://librivox.org/the-art-of-the-moving-picture-by-vachel-lindsay/).
LibriVox states that [its recordings are public domain in the USA](https://librivox.org/pages/public-domain/).
The [Project Gutenberg text](https://www.gutenberg.org/ebooks/13029) supplies an
independent written reference; it is never substituted for the recognized words.

The other excerpts come from Encyclopaedia Britannica Films' 1954
[*Making Films That Teach*](https://archive.org/details/MakingFi1954), explicitly
marked Public Domain by Prelinger/Internet Archive. Its machine-generated
subtitles were used only to locate passages, not as ground truth or as input to
CutNotes. Archival sound is not a pristine microphone recording.

These are relevant speech controls, not modern voice notes dictated to a computer.
They do not contain spoken cut timecodes. They cannot establish timestamp
acceptance or performance on spontaneous dictation. Existing synthetic timestamp
regressions and the original noisy recording remain separate tests. No timestamps
are inserted into the audio, and recording offsets must never become cut times.

## Reproduction and review

1. Download the two MP3s from the manifest; verify their SHA-256 hashes before use.
2. Create each contiguous excerpt with the bundled FFmpeg: `-ss START -i INPUT
   -t DURATION -ac 1 -ar 16000 -c:a pcm_s16le OUTPUT.wav`. Duration is end minus
   start. Do not denoise, normalize, splice or synthesize speech.
3. Run the bundled CLI's existing `import` command with explicit `--transcriber
   parakeet --formatter apple --language en --json --progress-fd 3`, a distinct
   title and a fresh output directory. Preserve the result, progress, session,
   audio, transcript, transcription evidence and Markdown.
4. Compare the audio with its unedited transcript, then the transcript with its
   unedited notes. Check distinct observations, praise, caveats, optionality,
   meaning, readable formatting and absence of invented timecodes. A complete
   process result is not a content-quality pass.
5. Run `python3 scripts/test.py` separately. Jev remains the default evaluator for
   its allowlisted public synthetic cases. These downloaded audio controls are
   reviewed locally; they do not bypass the evaluator's custom-source restriction.

Local evidence and the user review are retained under
`build/diagnostics/release-1.0.5/clean-audio-review-20260922/`. `sources.json`
includes every prepared excerpt, including an excluded preliminary script clip
whose endpoint interrupted a sentence. `results/` retains initial runs and
`final-results/` retains fresh runs after the citation-cleanup fix. Neither is
hand-edited into a better result. `review.md` and `review.html` provide the review
packet when the runs complete. Audio binaries remain outside Git and the app.

## Changes prompted by this review

Quiet-place and headphone guidance now appears in Record and Import, the guided
CLI and the README. The advice does not promise that noise is the only source of
formatting errors.

An initial native result exposed parenthesized source citations inside sentences
that left `()` and `(, ,)` after source-ID removal. The shared draft decoder now
removes complete citation-only groups wherever they occur. Its regression test
also preserves meaningful parentheses such as “if possible.” No model, prompt,
provider policy or macOS availability requirement changes in this fix.

The user must manually accept concrete output before publication. Signing,
notarization, DMG and updater validation, and post-release cleanup remain separate
steps. Native macOS 26 and Core Advanced output quality remain untested here.
