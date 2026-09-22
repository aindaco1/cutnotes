# CLI Machine Protocol

The app launches the bundled CLI with an argument array; no shell command is constructed. It passes `--json --progress-fd 3` for all app workflows and `--control-fd 4` for recording.

## Result

Standard output contains exactly one `cutnotes.result.v1` JSON object after success. It identifies the command and providers and includes absolute session, audio, transcript, and Markdown paths. Legacy top-level path keys remain during the v1 compatibility window.

## Error

Expected failures write one `cutnotes.error.v1` JSON object as the final standard-error line and exit nonzero. The object includes a stable code, user-facing message, recovery action, numeric exit code, and booleans stating whether audio and transcript artifacts were preserved.

`formatter_incomplete` means that some notes were usable but at least one timed
source passage or detected video time was left unrepresented. It does not write a
success result or replace existing Markdown. The error retains the v1 field types;
Python preservation tests and Swift decoding tests cover the additional code.

## Progress

Descriptor 3 is newline-delimited `cutnotes.progress.v1` JSON. Sequence numbers begin at zero and increase monotonically. Event kinds are `stage`, `progress`, or `warning`; fractions are clamped to 0 through 1; messages are whitespace-normalized and bounded to 240 characters. A closed progress pipe is advisory and cannot abort the workflow.

## Recording control

Descriptor 4 accepts only newline-terminated `pause`, `resume`, `finish`, and `cancel` commands. `pause` closes the active fixed-format WAV segment normally, and `resume` begins the next segment in the same session. `finish` closes the active segment and joins every captured segment into one WAV without inserting paused time. `cancel` interrupts active capture, joins any usable segments, and returns an error describing the preserved audio. Repeated `pause` or `resume` commands are harmless. A closed control descriptor finishes safely. Noninteractive recording without this descriptor is rejected.

## Diagnostics and capabilities

`doctor --json` returns one `cutnotes.doctor.v1` object. The ordered `parakeet.languages` array contains `{ "code", "name" }` entries for every language exposed by the selected Parakeet model. `cutnotes_core` owns this capability list; the app renders the supplied native names and passes only the selected code back to the CLI.

MacWhisper discovery is passive: `macwhisper.path` reports the available CLI, while `version` remains null and `models` remains an empty array. Setup never runs `mw version` or `mw models`, because those commands can launch MacWhisper. The pipeline invokes `mw transcribe` only when MacWhisper is explicitly selected. These values retain the v1 field types.

On macOS 27, helpers built with Xcode 27 also return an optional `apple.model`
object in `cutnotes.local.status.v1`, passed through as `local_engine.apple.model`
and `apple_formatter.model` in doctor output. It contains `name`, `context_size`
(tokens), and a `capabilities` string array. This is passive system-model metadata;
it performs no generation and contains no user content. Older helpers, SDKs and
systems omit it. Missing metadata means unknown, not unsupported. Consumers must
continue to accept legacy status payloads. The native helper and Swift app share
this Codable definition; Python preserves it for local acceptance reports.

## Optional transcription evidence

The native `transcribe` operation accepts `--evidence-output PATH` alongside its
unchanged `cutnotes.local.transcript.v1` output. The companion uses
`cutnotes.local.transcript-evidence.v1`: `text`, `duration_seconds`, `tokens`
(`text`, `start`, `end`, `confidence`) and `words` (`text`, `start`, `end`). Offsets
are seconds in that audio chunk, not CUT timecodes. Confidence is retained as
reported, including low-confidence negations; it is not an instruction to delete
or correct words. Older native helpers may ignore the optional argument.

The core checks the schema, transcript match, finite numbers, confidence range,
and recording bounds. When every chunk supplies valid data, it translates offsets
into the complete recording and saves `<transcript-stem>.evidence.json` with
`cutnotes.transcript-evidence.v1`, the merged duration/tokens/words, and SHA-256
digests of the exact saved transcript and source audio. This file is installed
atomically without replacing an existing artifact. Missing or invalid optional
evidence does not invalidate a usable transcript. The result/progress contracts
are unchanged. The Apple formatter may use this exact alignment with known source audio to
exclude sustained very quiet utterances from its input, retaining an audit of
those decisions. The saved transcript is never changed; evidence does not select
another provider. Standalone text formatting does not infer an audio source.

## Apple editorial generation

`CutNotesLocal generate` accepts `--mode editorial-decision`, `editorial-text`,
or `editorial-edit`, along with UTF-8 `--prompt`, `--instructions`, and `--output`
paths. Instructions are separate from untrusted source/context at the model
boundary. Each response is `{"schema_version":"cutnotes.local.editorial.v1",
"result":{...}}`, with Boolean `answer` for decisions or nonempty string `text`
for the other modes. Both languages test the payload types. Invalid envelopes,
missing values, unavailable models, and timeouts fail explicitly; only bounded
context/guardrail refusals retain source wording for review. The matching helper
ships with the app. No silent old-helper or provider fallback is allowed.
The existing plan/draft contracts and outer CLI result/error schemas are unchanged.

Each successful Apple formatting run saves a unique local
`<notes-stem>.formatting-review-<id>.json` beside the Markdown. It includes the
source transcript/output hashes, source sentences, rejected revisions, relevance
exclusions, and available acoustic evidence. It contains private text and is not
telemetry or an input to remote development evaluation.

## Compatibility rule

Additive fields may be introduced within v1. Removing a field, changing its type, or changing descriptor semantics requires a new schema version plus Python producer and Swift consumer tests.
