# Release

Public CutNotes releases are arm64, Developer ID signed, notarized, stapled apps inside Developer ID signed, notarized, stapled DMGs published with a signed Sparkle appcast on GitHub Releases. An unsigned, unnotarized, or unstapled app or DMG is not a release candidate.

## One-time secrets

Keep all secrets outside Git:

- `CUTNOTES_SIGNING_IDENTITY`: a valid `Developer ID Application: …` identity.
- Notarization: either `CUTNOTES_NOTARY_PROFILE`, or the API-key trio `CUTNOTES_NOTARY_KEY`, `CUTNOTES_NOTARY_KEY_ID`, and `CUTNOTES_NOTARY_ISSUER`.
- Sparkle: the private key in Keychain account `com.dustwave.cutnotes`, or `CUTNOTES_SPARKLE_PRIVATE_KEY` in CI.

The public Sparkle key is committed in `config/sparkle-public-key.txt`. Never export or commit its private half.

Production support-report submission is additionally gated by the exact bundle identifier `com.dustwave.cutnotes`, a non-debug build, and `CutNotesSupportReportsEnabled=true` in the signed app. The review sheet must show the exact payload before any network request. Verify the relay separately; a successful app build does not establish GitHub issue delivery.

## Local candidate

```bash
export CUTNOTES_SIGNING_IDENTITY='Developer ID Application: Example (TEAMID)'
export CUTNOTES_NOTARY_PROFILE='cutnotes-notary'
./scripts/release/release.sh 1.0.2
```

The script verifies version agreement, runs both test suites, builds the pinned LGPL FFmpeg runtime and app, and signs every nested executable. It then notarizes, staples, and Gatekeeper-validates the app before packaging it; signs, notarizes, staples, and Gatekeeper-validates the DMG separately; signs the Sparkle update archive; and writes checksums. App and DMG submissions are distinct release gates.

## GitHub release

Push an annotated `v1.0.2` tag only after local acceptance. `.github/workflows/release.yml` repeats the release pipeline using repository secrets and uploads:

- `CutNotes-1.0.2-arm64.dmg`
- `appcast.xml`
- `SHA256SUMS`

The app feed is `https://github.com/aindaco1/cutnotes/releases/latest/download/appcast.xml`.

## Manual acceptance

After publishing, download the GitHub asset rather than reusing the local file. Verify its checksum, the DMG ticket, the enclosed app ticket, mount, copy, first launch, model setup, one real import, terminal command installation, top-right manual update check, reviewed support-report preview, deployed relay receipt, and absence of profiling. Record these as separate evidence. For 1.0.1 and later, also perform a real update from the immediately previous public app.
