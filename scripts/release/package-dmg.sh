#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
version="$("$root_dir/scripts/check-version.sh" "${1:-}")"
identity="${CUTNOTES_SIGNING_IDENTITY:-}"
dist_dir="$root_dir/dist"
pending_dmg="$dist_dir/CutNotes-$version-arm64.pending-notarization.dmg"
final_dmg="$dist_dir/CutNotes-$version-arm64.dmg"

if [[ -z "$identity" || "$identity" == "-" ]]; then
  echo "CUTNOTES_SIGNING_IDENTITY must name a Developer ID Application identity." >&2
  exit 3
fi
if ! /usr/bin/security find-identity -v -p codesigning | /usr/bin/grep -Fq "$identity"; then
  echo "The requested Developer ID Application identity is not available." >&2
  exit 3
fi

CUTNOTES_SIGNING_IDENTITY="$identity" "$root_dir/scripts/macos/build-app.sh" release
app_bundle="$(/usr/bin/readlink "$dist_dir/CutNotes.app")"
if [[ ! -d "$app_bundle" ]]; then
  echo "The signed app bundle was not produced." >&2
  exit 4
fi

stage_dir="$(mktemp -d)"
trap 'hdiutil detach "$stage_dir/mount" >/dev/null 2>&1 || true; rm -rf "$stage_dir"' EXIT
/usr/bin/ditto --norsrc --noextattr "$app_bundle" "$stage_dir/CutNotes.app"
/bin/ln -s /Applications "$stage_dir/Applications"
mkdir -p "$dist_dir"
rm -f "$pending_dmg"
/usr/bin/hdiutil create \
  -fs HFS+ \
  -format UDZO \
  -imagekey zlib-level=9 \
  -srcfolder "$stage_dir" \
  -volname CutNotes \
  "$pending_dmg"
/usr/bin/codesign --force --sign "$identity" --timestamp "$pending_dmg"
/usr/bin/codesign --verify --verbose=2 "$pending_dmg"

notary_arguments=(submit "$pending_dmg" --wait)
if [[ -n "${CUTNOTES_NOTARY_PROFILE:-}" ]]; then
  notary_arguments+=(--keychain-profile "$CUTNOTES_NOTARY_PROFILE")
elif [[ -n "${CUTNOTES_NOTARY_KEY:-}" && -n "${CUTNOTES_NOTARY_KEY_ID:-}" && -n "${CUTNOTES_NOTARY_ISSUER:-}" ]]; then
  notary_arguments+=(
    --key "$CUTNOTES_NOTARY_KEY"
    --key-id "$CUTNOTES_NOTARY_KEY_ID"
    --issuer "$CUTNOTES_NOTARY_ISSUER"
  )
else
  echo "Signed candidate created at $pending_dmg" >&2
  echo "Notarization credentials are required before it can become a release DMG." >&2
  exit 5
fi

/usr/bin/xcrun notarytool "${notary_arguments[@]}"
/usr/bin/xcrun stapler staple "$pending_dmg"
/usr/bin/xcrun stapler validate "$pending_dmg"
rm -f "$final_dmg"
/bin/mv "$pending_dmg" "$final_dmg"
/usr/sbin/spctl --assess --type open --context context:primary-signature --verbose=2 "$final_dmg"
echo "$final_dmg"
