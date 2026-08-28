# Privacy

CutNotes is designed for local editorial work.

- Recording, probing, conversion, chunking, Parakeet transcription, and Apple formatting run on the Mac.
- The app has no account system, telemetry, analytics, ad SDK, crash reporter, or first-party upload endpoint.
- Sparkle sends the normal update request to GitHub Releases. System profiling is disabled.
- Diagnostics export versions, readiness states, architecture, and stable error reasons. It excludes transcripts, prompts, titles, project paths, media paths, microphone names, environment variables, credentials, and command output.
- Original imported media is never modified. Failed later stages preserve completed audio or transcript artifacts and report that state explicitly.

MacWhisper and Codex CLI are separately installed, optional tools. Selecting one delegates that stage to the tool under its own settings and privacy behavior. CutNotes never silently switches to either provider.

The Parakeet setup performs one explicit HTTPS download from the pinned Hugging Face model repository. Model weights are verified locally and remain in Application Support.
