# CLI Machine Protocol

The app launches the bundled CLI with an argument array; no shell command is constructed. It passes `--json --progress-fd 3` for all app workflows and `--control-fd 4` for recording.

## Result

Standard output contains exactly one `cutnotes.result.v1` JSON object after success. It identifies the command and providers and includes absolute session, audio, transcript, and Markdown paths. Legacy top-level path keys remain during the v1 compatibility window.

## Error

Expected failures write one `cutnotes.error.v1` JSON object as the final standard-error line and exit nonzero. The object includes a stable code, user-facing message, recovery action, numeric exit code, and booleans stating whether audio and transcript artifacts were preserved.

## Progress

Descriptor 3 is newline-delimited `cutnotes.progress.v1` JSON. Sequence numbers begin at zero and increase monotonically. Event kinds are `stage`, `progress`, or `warning`; fractions are clamped to 0 through 1; messages are whitespace-normalized and bounded to 240 characters. A closed progress pipe is advisory and cannot abort the workflow.

## Recording control

Descriptor 4 accepts only newline-terminated `finish` and `cancel` commands. `finish` asks FFmpeg to close the recording normally. `cancel` interrupts capture and returns an error describing any preserved audio. Noninteractive recording without this descriptor is rejected.

## Compatibility rule

Additive fields may be introduced within v1. Removing a field, changing its type, or changing descriptor semantics requires a new schema version plus Python producer and Swift consumer tests.
