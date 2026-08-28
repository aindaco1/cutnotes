# CutNotes Engineering Contract

## Authority

- `cutnotes_core` is the sole authority for capture, limits, chunking, transcription, formatting, output allocation, preservation, and provider selection.
- The root `cutnotes` executable is a compatibility launcher and re-export surface.
- Swift builds argument arrays and consumes versioned contracts. It must never parse human-readable terminal text or duplicate pipeline policy.

## Machine interface

- App commands always pass `--json --progress-fd 3`; recording also passes `--control-fd 4`.
- Descriptor 3 is bounded NDJSON progress. Descriptor 4 accepts only `finish` or `cancel` lines.
- Standard output is one final JSON result. Expected failures are one final JSON error on standard error with a stable code and preserved-artifact flags.
- Machine schema changes require Python and Swift decoding tests and a schema version change when compatibility is broken.

## Product invariants

- Default transcription is local Parakeet v3; default formatting is Apple on-device when available.
- MacWhisper and Codex CLI are explicit optional providers. Never add silent provider fallback.
- User source media is read-only. Sessions never overwrite prior artifacts.
- Four hours is the hard cap; recording warns at 3:45.
- No telemetry, profiling, analytics, or first-party upload path.
- Keep the CLI fully usable without the app.

## Release gates

- Run Python tests, Swift tests, app bundle validation, real Parakeet transcription, Apple formatting where available, Developer ID signing, notarization, stapling, DMG mount/install/launch, and Sparkle signature/feed checks as distinct gates.
- Do not publish an unsigned or unnotarized public release.
- Never commit signing certificates, notarization keys, Sparkle private keys, or model weights.
