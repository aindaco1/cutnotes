# CutNotes

CutNotes turns spoken rough-cut feedback into a local transcript and, when requested, structured Markdown notes. It ships as both a native Apple Silicon Mac app and the original command-line tool. The Python CLI remains the single workflow authority; the SwiftUI app is a small, typed client of that same CLI.

CutNotes is free, open-source software under the MIT License.

## What 1.0 does

- **Record** a voice-note session from a selected microphone.
- **Import** any audio or video file that the bundled FFmpeg can read.
- **Format** an existing UTF-8 plain-text transcript.
- Transcribe locally with the pinned Parakeet TDT 0.6B v3 Core ML model.
- Format locally with Apple Intelligence when the system model is available.
- Optionally use an installed MacWhisper CLI for transcription or Codex CLI for formatting.
- Preserve audio and transcripts when a later stage fails.
- Save every session without overwriting an earlier one.

The maximum recording or imported-media duration is four hours. Recording warns at 3 hours 45 minutes and stops at 4 hours; imports longer than four hours are rejected before transcription.

## Import format, in plain language

There are two kinds of import:

1. `cutnotes import` accepts an existing **audio or video** file. CutNotes checks its duration, converts it into 15-minute mono audio chunks, transcribes each chunk, joins the transcript, and optionally formats the result. The original file is never modified. A project title is required.
2. `cutnotes format` accepts an existing **UTF-8 `.txt` transcript**. It does no transcription; it only creates the structured Markdown notes. A title is required.

Examples:

```bash
cutnotes import ~/Desktop/review.m4a --title "Episode 4 Rough Cut"
cutnotes import ~/Desktop/review.mov --title "Episode 4" --transcript-only
cutnotes format ~/Desktop/transcript.txt --title "Episode 4 Rough Cut"
```

The app exposes the same distinction as the **Import** and **Format** buttons.

## Mac app

CutNotes 1.0 requires Apple Silicon and macOS 15 or later. Apple on-device formatting additionally requires macOS 26, Apple Intelligence enabled, and an available system language model. On other supported systems, transcript-only and Codex formatting remain available.

The app bundles its pinned Python, FFmpeg, FFprobe, native helper, and CLI. It does not bundle the roughly 483 MB Parakeet weights. The first-run setup downloads those exact weights only after license acceptance, verifies every file with SHA-256, then stores them in:

```text
~/Library/Application Support/CutNotes/Models/parakeet-tdt-0.6b-v3/
```

Use **CutNotes > Install cutnotes Command…** after moving the app to `/Applications`. The administrator prompt creates only this stable link:

```text
/usr/local/bin/cutnotes -> /Applications/CutNotes.app/Contents/Resources/CLI/bin/cutnotes
```

## CLI quick start

```bash
cutnotes doctor
cutnotes model download
cutnotes record "Project — Rough Cut"
```

Running `cutnotes` without a subcommand starts guided terminal mode. During terminal recording, press `q` to finish. In the app, use **Finish Recording** or **Cancel**.

Default output:

```text
~/Desktop/<Project Name>/
├── voice-notes.wav
├── transcript.txt
├── <project-name>.md
└── session.json
```

New sessions receive timestamped names rather than replacing existing files.

Useful explicit provider choices:

```bash
# Fully local transcript only
cutnotes import review.mov --title "Rough Cut" --transcript-only

# Optional MacWhisper transcription
cutnotes import review.m4a --title "Rough Cut" --transcriber macwhisper

# Optional Codex CLI formatting; no automatic fallback
cutnotes format transcript.txt --title "Rough Cut" --formatter codex
```

CutNotes exposes all 25 languages listed by the official Parakeet v3 model, using their native names in the app. English is fully supported in CutNotes 1.0; the other 24 languages remain experimental at the CutNotes product layer. Run `cutnotes <command> --help` for all advanced options.

## Privacy

Parakeet transcription and Apple formatting run on the Mac. CutNotes has no telemetry, analytics, accounts, or first-party upload service. Selecting Codex CLI or MacWhisper delegates only that stage to the separately installed tool and its own configuration. No provider fallback happens silently. See [docs/PRIVACY.md](docs/PRIVACY.md).

## Build and test

Requirements: Apple Silicon, Xcode 26, Swift 6, Homebrew Python 3.14.6, and standard macOS build tools.

```bash
python3 -m unittest discover -s tests -v
swift test --package-path macos
./script/build_and_run.sh --verify
```

The canonical desktop Run action is `./script/build_and_run.sh`. Release details are in [docs/RELEASE.md](docs/RELEASE.md); the architecture and machine contracts are in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/CLI_PROTOCOL.md](docs/CLI_PROTOCOL.md).

## Contributing

Keep workflow behavior in `cutnotes_core`. Swift may build typed argument arrays and render versioned JSON contracts, but it must not duplicate pipeline policy or parse terminal prose. Add or update both Python and Swift contract tests when a machine field changes.

Third-party licensing and model attribution are listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
