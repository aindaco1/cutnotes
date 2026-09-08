# Privacy

CutNotes is designed for local editorial work.

- Recording, probing, conversion, chunking, Parakeet transcription, and Apple formatting run on the Mac.
- The app has no account system, telemetry, analytics, ad SDK, or automatic crash upload.
- Sparkle sends the normal update request to GitHub Releases. System profiling is disabled.
- Diagnostics export versions, readiness states, architecture, and stable error reasons. It excludes transcripts, prompts, titles, project paths, media paths, microphone names, environment variables, credentials, and command output.
- **Report a Problem** first shows the exact JSON that would be sent. Opening the review sends nothing. The user must explicitly choose **Send Reviewed Reports**.
- A reviewed report contains a bounded current-state projection and, when present, up to five summaries of CutNotes crash incidents from the last 14 days. Crash summaries contain only the exception, signal, an allowlisted image name, a relative image offset, and numeric app/OS/architecture fields. Raw incident files and stacks never enter the preview or request.
- Reviewed reports go to `https://crash.dustwave.xyz/v1/cutnotes/reports`, which validates the same strict schema, rate-limits intake, and creates or updates matching issues in the public CutNotes GitHub repository. The app contains no GitHub credential. Failed sends retain unsent reports locally for explicit retry.
- Original imported media is never modified. Failed later stages preserve completed audio or transcript artifacts and report that state explicitly.

MacWhisper and Codex CLI are separately installed, optional tools. Selecting one delegates that stage to the tool under its own settings and privacy behavior. CutNotes never silently switches to either provider.

The Parakeet setup performs one explicit HTTPS download from the pinned Hugging Face model repository. Model weights are verified locally and remain in Application Support.
