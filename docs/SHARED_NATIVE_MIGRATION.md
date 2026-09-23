# Shared native migration

The local helper uses `DustWaveSpeech` and `DustWaveAppleIntelligence` from
`shared/dust-wave-platform/native`. This replaces its Record package dependency;
the Python authority, machine schemas, source files, optional providers, editorial
prompts and response budgets are unchanged. FluidAudio remains exactly 0.15.6.
Platform's [native ADR](../shared/dust-wave-platform/docs/adr/0004-native-speech-and-apple-generation.md)
describes the common ownership boundary.

Initialize dependencies with `git submodule update --init --recursive`, then run
`python3 scripts/test.py`. Preserve the fixed corpus, Jev controls/questions and
margin when comparing with the baseline. Exact/native failures and Jev review
remain visible; compilation does not establish formatting acceptance.

Rollback reverts the gitlink, Swift manifest/lockfile, helper adapter and license
packaging changes together. No user data or model files change. The original migration did not include an app release. The subsequent 1.0.6
release request includes this migration; its validation is recorded in
[the release acceptance record](RELEASE_1_0_6_ACCEPTANCE.md).
