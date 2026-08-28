# Changelog

## 1.0.0 — Unreleased

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
