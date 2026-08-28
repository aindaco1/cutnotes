# Release

Public CutNotes releases are arm64, Developer ID signed, notarized, stapled DMGs published with a signed Sparkle appcast on GitHub Releases. An unsigned or unstapled artifact is not a release candidate.

## One-time secrets

Keep all secrets outside Git:

- `CUTNOTES_SIGNING_IDENTITY`: a valid `Developer ID Application: …` identity.
- Notarization: either `CUTNOTES_NOTARY_PROFILE`, or the API-key trio `CUTNOTES_NOTARY_KEY`, `CUTNOTES_NOTARY_KEY_ID`, and `CUTNOTES_NOTARY_ISSUER`.
- Sparkle: the private key in Keychain account `com.dustwave.cutnotes`, or `CUTNOTES_SPARKLE_PRIVATE_KEY` in CI.

The public Sparkle key is committed in `config/sparkle-public-key.txt`. Never export or commit its private half.

## Local candidate

```bash
export CUTNOTES_SIGNING_IDENTITY='Developer ID Application: Example (TEAMID)'
export CUTNOTES_NOTARY_PROFILE='cutnotes-notary'
./scripts/release/release.sh 1.0.0
```

The script verifies version agreement, runs both test suites, builds the pinned LGPL FFmpeg runtime and app, signs every nested executable, creates and signs the DMG, submits it to Apple, staples it, validates Gatekeeper, signs the update archive with Sparkle, and writes checksums.

## GitHub release

Push an annotated `v1.0.0` tag only after local acceptance. `.github/workflows/release.yml` repeats the release pipeline using repository secrets and uploads:

- `CutNotes-1.0.0-arm64.dmg`
- `appcast.xml`
- `SHA256SUMS`

The app feed is `https://github.com/aindaco1/cutnotes/releases/latest/download/appcast.xml`.

## Manual acceptance

After publishing, download the GitHub asset rather than reusing the local file. Verify its checksum, notarization ticket, mount, copy, first launch, model setup, one real import, terminal command installation, manual update check, and absence of profiling. Record these as separate evidence. For 1.0.1 and later, also perform a real update from the immediately previous public app.
