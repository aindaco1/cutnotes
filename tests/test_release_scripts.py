from __future__ import annotations

from pathlib import Path
import unittest


PROJECT_DIR = Path(__file__).resolve().parents[1]


class ReleaseScriptTests(unittest.TestCase):
    def test_app_is_notarized_and_stapled_before_dmg_creation(self) -> None:
        script = (PROJECT_DIR / "scripts/release/package-dmg.sh").read_text(
            encoding="utf-8"
        )

        app_submit = script.index('notarize_and_wait "$app_submission" "App"')
        app_staple = script.index('stapler staple "$app_bundle"')
        app_ticket_validation = script.index('stapler validate "$app_bundle"')
        dmg_creation = script.index("hdiutil create")
        dmg_submit = script.index('notarize_and_wait "$pending_dmg" "DMG"')

        self.assertLess(app_submit, app_staple)
        self.assertLess(app_staple, app_ticket_validation)
        self.assertLess(app_ticket_validation, dmg_creation)
        self.assertLess(dmg_creation, dmg_submit)

    def test_release_verification_requires_both_stapled_tickets(self) -> None:
        script = (PROJECT_DIR / "scripts/release/verify-release.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn('stapler validate "$dmg"', script)
        self.assertIn('stapler validate "$app"', script)


if __name__ == "__main__":
    unittest.main()
