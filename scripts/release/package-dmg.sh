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

work_root="$(mktemp -d /private/tmp/cutnotes-release.XXXXXX)"
trap 'rm -rf "$work_root"' EXIT
credential_arguments=()
if [[ -n "${CUTNOTES_NOTARY_PROFILE:-}" ]]; then
  credential_arguments+=(--keychain-profile "$CUTNOTES_NOTARY_PROFILE")
elif [[ -n "${CUTNOTES_NOTARY_KEY:-}" && -n "${CUTNOTES_NOTARY_KEY_ID:-}" && -n "${CUTNOTES_NOTARY_ISSUER:-}" ]]; then
  notary_key="$work_root/notary-key.p8"
  /bin/cp "$CUTNOTES_NOTARY_KEY" "$notary_key"
  /bin/chmod 600 "$notary_key"
  credential_arguments+=(
    --key "$notary_key"
    --key-id "$CUTNOTES_NOTARY_KEY_ID"
    --issuer "$CUTNOTES_NOTARY_ISSUER"
  )
else
  echo "Notarization credentials are required before creating a release candidate." >&2
  exit 5
fi

notarize_and_wait() {
  local artifact="$1"
  local label="$2"
  local submission_output submission_id status_output notary_status

  submission_output="$(
    /usr/bin/xcrun notarytool submit "$artifact" \
      --no-wait --no-progress \
      "${credential_arguments[@]}"
  )"
  printf '%s\n' "$submission_output"
  submission_id="$(
    printf '%s\n' "$submission_output" \
      | /usr/bin/sed -n 's/^[[:space:]]*id: \([^[:space:]]*\)$/\1/p'
  )"
  if [[ -z "$submission_id" ]]; then
    echo "$label notarization upload did not return a submission ID." >&2
    exit 6
  fi
  echo "$label notarization submission: $submission_id" >&2

  notary_status=""
  for ((attempt = 1; attempt <= 1080; attempt++)); do
    if ! status_output="$(
      /usr/bin/xcrun notarytool info "$submission_id" "${credential_arguments[@]}"
    )"; then
      echo "$label notarization status check failed transiently; retrying." >&2
      /bin/sleep 10
      continue
    fi
    notary_status="$(
      printf '%s\n' "$status_output" \
        | /usr/bin/sed -n 's/^[[:space:]]*status: \(.*\)$/\1/p'
    )"
    case "$notary_status" in
      Accepted)
        printf '%s\n' "$status_output"
        return 0
        ;;
      "In Progress")
        /bin/sleep 10
        ;;
      *)
        printf '%s\n' "$status_output" >&2
        echo "$label notarization failed with status: ${notary_status:-unknown}" >&2
        exit 6
        ;;
    esac
  done

  echo "$label notarization did not finish within 180 minutes." >&2
  exit 6
}

CUTNOTES_SIGNING_IDENTITY="$identity" "$root_dir/scripts/macos/build-app.sh" release
app_bundle="$(/usr/bin/readlink "$dist_dir/CutNotes.app")"
if [[ ! -d "$app_bundle" ]]; then
  echo "The signed app bundle was not produced." >&2
  exit 4
fi

app_submission="$work_root/CutNotes-notarization.zip"
COPYFILE_DISABLE=1 /usr/bin/ditto --norsrc --noextattr -c -k --keepParent \
  "$app_bundle" "$app_submission"
notarize_and_wait "$app_submission" "App"
/usr/bin/xcrun stapler staple "$app_bundle"
/usr/bin/xcrun stapler validate "$app_bundle"
/usr/sbin/spctl --assess --type execute --verbose=2 "$app_bundle"

dmg_source="$work_root/dmg-source"
/bin/mkdir -p "$dmg_source" "$dist_dir"
/usr/bin/ditto --norsrc --noextattr "$app_bundle" "$dmg_source/CutNotes.app"
/bin/ln -s /Applications "$dmg_source/Applications"
/bin/rm -f "$pending_dmg"
/usr/bin/hdiutil create \
  -fs HFS+ \
  -format UDZO \
  -imagekey zlib-level=9 \
  -srcfolder "$dmg_source" \
  -volname CutNotes \
  "$pending_dmg"
/usr/bin/codesign --force --sign "$identity" --timestamp "$pending_dmg"
/usr/bin/codesign --verify --verbose=2 "$pending_dmg"

notarize_and_wait "$pending_dmg" "DMG"
/usr/bin/xcrun stapler staple "$pending_dmg"
/usr/bin/xcrun stapler validate "$pending_dmg"
/usr/sbin/spctl --assess --type open --context context:primary-signature \
  --verbose=2 "$pending_dmg"
/bin/rm -f "$final_dmg"
/bin/mv "$pending_dmg" "$final_dmg"
echo "$final_dmg"
