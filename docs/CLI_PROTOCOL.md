# CLI Machine Protocol

The app launches the bundled CLI with an argument array; no shell command is constructed. It passes `--json --progress-fd 3` for all app workflows and `--control-fd 4` for recording.

## Result

Standard output contains exactly one `cutnotes.result.v1` JSON object after success. It identifies the command and providers and includes absolute session, audio, transcript, and Markdown paths. Legacy top-level path keys remain during the v1 compatibility window.

## Error

Expected failures write one `cutnotes.error.v1` JSON object as the final standard-error line and exit nonzero. The object includes a stable code, user-facing message, recovery action, numeric exit code, and booleans stating whether audio and transcript artifacts were preserved.

## Progress

Descriptor 3 is newline-delimited `cutnotes.progress.v1` JSON. Sequence numbers begin at zero and increase monotonically. Event kinds are `stage`, `progress`, or `warning`; fractions are clamped to 0 through 1; messages are whitespace-normalized and bounded to 240 characters. A closed progress pipe is advisory and cannot abort the workflow.

## Recording control

Descriptor 4 accepts only newline-terminated `pause`, `resume`, `finish`, and `cancel` commands. `pause` closes the active fixed-format WAV segment normally, and `resume` begins the next segment in the same session. `finish` closes the active segment and joins every captured segment into one WAV without inserting paused time. `cancel` interrupts active capture, joins any usable segments, and returns an error describing the preserved audio. Repeated `pause` or `resume` commands are harmless. A closed control descriptor finishes safely. Noninteractive recording without this descriptor is rejected.

## Diagnostics and capabilities

`doctor --json` returns one `cutnotes.doctor.v1` object. The ordered `parakeet.languages` array contains `{ "code", "name" }` entries for every language exposed by the selected Parakeet model. `cutnotes_core` owns this capability list; the app renders the supplied native names and passes only the selected code back to the CLI.

## Compatibility rule

Additive fields may be introduced within v1. Removing a field, changing its type, or changing descriptor semantics requires a new schema version plus Python producer and Swift consumer tests.
