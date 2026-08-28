# Testing

Run the fast gates first:

```bash
python3 -m unittest discover -s tests -v
swift test --package-path macos
./script/build_and_run.sh --verify
```

Release acceptance is deliberately split into separate claims:

1. Python unit/integration tests pass.
2. Swift command/contract tests pass.
3. The app bundle builds arm64 with the pinned runtime and no non-system absolute load paths.
4. A generated speech fixture transcribes through the bundled CLI and installed Parakeet model.
5. Apple formatting succeeds when the system model reports ready.
6. Optional MacWhisper and Codex selections either work or return provider-specific errors without fallback.
7. Developer ID signatures verify under strict/deep validation.
8. Apple notarization accepts the DMG and the ticket staples.
9. A clean mounted DMG can be copied to `/Applications`, launched, and used to install the terminal command.
10. The appcast signature verifies and a previously released app can discover, download, and install the new release.

For 1.0.0 there is no earlier Sparkle-enabled public version, so the real previous-version update hop becomes a mandatory 1.0.1 release gate. Feed generation and archive signatures are still required for 1.0.0.
