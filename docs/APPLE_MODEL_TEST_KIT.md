# Apple model test kit

Private development build of CutNotes 1.0.5. It is Developer ID signed but is
not a notarized release candidate. Keep the installed public app in place.
The formatter still has known content failures on AFM 3 Core; this kit measures
the same implementation on another Mac. It does not include the experimental
clause editor or any user recordings, and does not download model weights.

On an eligible Mac with macOS 27 and Apple Intelligence ready, extract the kit
and double-click **Run Apple checks.command**. No app installation, Xcode,
Homebrew or Parakeet download is needed for this formatting-only check.
If Gatekeeper prevents execution, stop and use a notarized candidate when
available; bypassing Gatekeeper is not part of this procedure.

The command checks the app signature and requires the helper to report
`AFM 3 Core Advanced` before inference. An unavailable or different model is a
failed prerequisite, never a successful Advanced test. The requirement checks
the OS-selected model; it cannot choose or force one. The same arm64 app supports
older Apple Silicon Macs and macOS 26, where new model metadata is optional.

The benchmark runs the public synthetic reviews bundled with the kit locally;
`manifest.json` records its case count and fixture hashes. It explicitly skips Jev
and needs no cloud credentials. Evaluate these saved public outputs with Jev from
the development checkout afterward. Results appear in a new
`CutNotes-Apple-Check.*` folder on the Desktop. `acceptance/report.json` records
the actual model, OS, hashes and content failures. Each case includes its input
and generated Markdown when formatting succeeds. Keep this entire results folder
for comparison. Passing pattern checks still requires reading the output for
invented claims, unrelated conversation, repetition and lost qualifications.

For a comparison on Core or macOS 26, run from Terminal:

```bash
"/path/to/test kit/Run Apple checks.command" --any-model
```

This removes only the model-name prerequisite, records whatever model is
reported, and uses the same fixtures and content checks. It does not enable a
fallback provider. The app UI and MacWhisper are not opened by the benchmark.

The private supplied recording needs a separate review on the target Mac;
synthetic checks alone cannot establish that recording's output quality.

Developers can reproduce the kit after building the app. Stage the directory
outside iCloud to avoid Finder metadata invalidating the copied app signature;
the resulting ZIP can be stored in iCloud:

```bash
scripts/macos/prepare-apple-test-kit.sh dist/CutNotes.app /new/test-kit-directory
```

Apple determines the available model from the device and OS. See
[Apple's model-selection clarification](https://developer.apple.com/forums/thread/832555/).
