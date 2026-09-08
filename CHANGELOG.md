# Changelog

## 1.0.2 — 2026-09-07

- Fixes the installed `/usr/local/bin/cutnotes` command so the bundled launcher resolves its application symlink before locating the self-contained Python and media runtimes.
- Moves the signed GitHub Releases update check from the app menu to a top-right toolbar icon.
- Adds an explicit review-before-send support flow for a bounded current-state report and privacy-safe summaries of recent CutNotes crashes. Matching reports are aggregated in public GitHub issues; project names, editorial context, media, transcripts, paths, device names, raw logs, and crash stacks are excluded.

## 1.0.1 — 2026-09-07

- Splits large Apple on-device formatting work into context-safe source batches, retries rejected batches at a smaller size, and preserves isolated guardrail-rejected passages through deterministic local rendering without exposing internal Foundation Models errors.
- Replaces sentence-dump formatting with a concise Notion-style feedback summary and chronological timestamped notes. The core normalizes common spoken timecode forms before provider use, groups adjacent edit points, rejects cross-time or contradictory drafts, and handles clear rough-cut patterns locally while Apple or Codex rewrites unstructured prose.
- Adds pause and resume for app recordings. Pauses finalize lossless WAV segments, exclude paused time from the four-hour captured-audio cap, and rejoin the session without inserted silence.
- Updates the bundled Python runtime to 3.14.7.

## 1.0.0 — 2026-08-28

- Adds the native Apple Silicon SwiftUI app for record, import, and format workflows.
- Adds a native-name dropdown for all 25 Parakeet v3 languages and rounded monochrome panels.
- Makes local Parakeet TDT 0.6B v3 transcription the default with explicit, pinned, hash-verified model setup.
- Makes Apple Foundation Models the default formatter when available.
- Limits Apple Intelligence to source-ID classification and renders note text deterministically to prevent unsupported edits.
- Retains MacWhisper and Codex CLI as explicit optional providers without silent fallback.
- Adds versioned JSON result/error/progress contracts and a dedicated recording control channel.
- Adds the four-hour limit, 3:45 warning, 15-minute transcription chunks, preservation metadata, and collision-safe sessions.
- Bundles pinned Python, FFmpeg, FFprobe, and the native local helper.
- Adds terminal command installation, privacy-safe diagnostics, Developer ID release packaging, notarization gates, and signed Sparkle updates.
