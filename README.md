# cutnotes

`cutnotes` records rough-cut feedback, transcribes it locally with MacWhisper, and asks Codex to turn the transcript into a polished Markdown document ready to import or paste into Notion.

## Install

On this Mac, the launcher is installed at `/opt/homebrew/bin/cutnotes`, which is
already on the terminal `PATH`.

For another Mac, open the extracted `cutnotes` folder and run:

```bash
chmod +x cutnotes
ln -s "$(pwd)/cutnotes" /opt/homebrew/bin/cutnotes
```

## Quick start

```bash
cutnotes
```

Running `cutnotes` starts a guided session:

1. Checks FFmpeg, MacWhisper, Codex, the active model, and the microphone.
2. Prompts for the project or cut name.
3. Waits until you are ready to begin recording.
4. Records one continuous voice-note session.
5. Transcribes locally with MacWhisper.
6. Uses Codex to organize and summarize the notes.
7. Creates a Notion-ready Markdown file inside a Desktop project folder.

Use headphones while watching the cut. Begin each thought with the cut timecode:

> “Timestamp 12 minutes 34 seconds. The reaction shot runs too long.”

Press `q` when the session is finished. Transcription and formatting begin automatically.

Files are saved directly in a directory named after the project:

```text
~/Desktop/<Project Name>/
```

The first session creates:

- `voice-notes.wav`
- `transcript.txt`
- the final `.md` file
- `session.json`

If that project folder already contains a session, new filenames receive a
timestamp so earlier recordings and notes are never overwritten.

## Advanced commands

### Record, transcribe, and format

```bash
cutnotes record "Project — Rough Cut Feedback"
```

Useful options:

```bash
cutnotes record "Project — Rough Cut Feedback" \
  --context "Correct names: Kaidin, Mia, Jordan" \
  --mic "MacBook Pro Microphone" \
  --language en
```

### Process an existing recording

```bash
cutnotes import ~/Desktop/voice-notes.m4a \
  --title "Project — Rough Cut Feedback"
```

### Reformat an existing transcript

```bash
cutnotes format transcript.txt \
  --title "Project — Rough Cut Feedback" \
  --output feedback.md
```

### Transcribe locally without Codex

```bash
cutnotes record "Project — Rough Cut Feedback" --transcript-only
```

### Check the setup

```bash
cutnotes doctor
```

`doctor` reports the installed versions, MacWhisper models, and available microphones.

## Privacy

- Recording and transcription run locally through FFmpeg and MacWhisper.
- The formatting step sends the transcript to Codex using the account and provider configured in the local Codex CLI.
- Use `--transcript-only` if the transcript should remain entirely local.

## Configuration

The following environment variables override discovery and defaults:

| Variable | Purpose |
|---|---|
| `CUTNOTES_ROOT` | Parent directory for project folders; defaults to `~/Desktop` |
| `CUTNOTES_FFMPEG` | FFmpeg executable |
| `CUTNOTES_MACWHISPER` | MacWhisper `mw` executable |
| `CUTNOTES_CODEX` | Codex executable |

The default MacWhisper path is:

```text
/Applications/MacWhisper.app/Contents/MacOS/mw
```

When available, `cutnotes` prefers the newer Codex executable bundled with the
ChatGPT/Codex desktop app over an older executable found on `PATH`.

Run `cutnotes --help` or `cutnotes <command> --help` for the full command reference.
