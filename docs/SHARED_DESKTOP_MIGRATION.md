# Shared desktop services migration

Source migration only; release and deployment acceptance remain separate.

- Consumer baseline: `a47a3c11749ce89b70e6ed17e8b8e99b352b56f2`.
- Previous Platform pin: `0affb6c5652611b87947bd87762d8aa17d35ea32`.
- New immutable commit and exact versions: [platform-desktop.json](../platform-desktop.json).
- Shared surface: Sparkle controller, bounded reviewed-report transport and acknowledgement validation.

Keep report schemas, consent, batch ordering, local failure messages, exact report-ID receipts and unsent reports in CutNotes.

## Validation

Before: support-report and consent characterization passed. After: `python3 scripts/test.py --offline` passed (Python and Swift).

All consumer gitlinks, exact package versions and retained Sparkle lockfile
revisions pass:

```sh
node shared/dust-wave-platform/scripts/check-desktop-consumer.mjs
```

Platform passes its JavaScript suite and clean-checkout recipe tests. Its seven
desktop Swift tests pass independently with Sparkle 2.9.5, 2.9.6 and 2.10.0.
App manifests retain their exact existing Sparkle revisions. Advancing the
full gitlink also carries existing Platform patches; product-owned tests
cover those dependencies.

## Independent rollback

Revert this repository's migration commit, then run
`git submodule update --init --recursive`. This restores the prior adapters,
dependency declaration, gitlink and build/CI configuration together. For a
newly added Platform submodule, Git may leave an untracked checkout directory;
it is no longer a build input after the revert.

No user data or relay storage migration is required. Other applications may
stay on their chosen Platform revisions. A reverse-patch check of the complete
migration records whether the source rollback applies cleanly.

Local source/build evidence does not establish notarization, a signed updater
replacement, physical hardware behavior or deployed GitHub delivery. Use the
existing release runbook before shipping.
