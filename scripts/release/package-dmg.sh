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

stage_dir="$(mktemp -d /private/tmp/cutnotes-release.XXXXXX)"
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

notary_dmg_name="$(basename "$pending_dmg")"
/bin/cp "$pending_dmg" "$stage_dir/$notary_dmg_name"
credential_arguments=()
if [[ -n "${CUTNOTES_NOTARY_PROFILE:-}" ]]; then
  credential_arguments+=(--keychain-profile "$CUTNOTES_NOTARY_PROFILE")
elif [[ -n "${CUTNOTES_NOTARY_KEY:-}" && -n "${CUTNOTES_NOTARY_KEY_ID:-}" && -n "${CUTNOTES_NOTARY_ISSUER:-}" ]]; then
  notary_key_name="$(basename "$CUTNOTES_NOTARY_KEY")"
  /bin/cp "$CUTNOTES_NOTARY_KEY" "$stage_dir/$notary_key_name"
  /bin/chmod 600 "$stage_dir/$notary_key_name"
  credential_arguments+=(
    --key "$notary_key_name"
    --key-id "$CUTNOTES_NOTARY_KEY_ID"
    --issuer "$CUTNOTES_NOTARY_ISSUER"
  )
else
  echo "Signed candidate created at $pending_dmg" >&2
  echo "Notarization credentials are required before it can become a release DMG." >&2
  exit 5
fi

submission_output="$(
  cd "$stage_dir"
  /usr/bin/xcrun notarytool submit "$notary_dmg_name" \
    --no-wait --no-progress --no-s3-acceleration \
    "${credential_arguments[@]}"
)"
printf '%s\n' "$submission_output"
submission_id="$(
  printf '%s\n' "$submission_output" \
    | /usr/bin/sed -n 's/^[[:space:]]*id: \([^[:space:]]*\)$/\1/p'
)"
if [[ -z "$submission_id" ]]; then
  echo "Notarization upload did not return a submission ID." >&2
  exit 6
fi

notary_status=""
for ((attempt = 1; attempt <= 180; attempt++)); do
  if ! status_output="$(
    cd "$stage_dir"
    /usr/bin/xcrun notarytool info "$submission_id" "${credential_arguments[@]}"
  )"; then
    echo "Notarization status check failed transiently; retrying." >&2
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
      break
      ;;
    "In Progress")
      /bin/sleep 10
      ;;
    *)
      printf '%s\n' "$status_output" >&2
      echo "Notarization failed with status: ${notary_status:-unknown}" >&2
      exit 6
      ;;
  esac
done
if [[ "$notary_status" != "Accepted" ]]; then
  echo "Notarization did not finish within 30 minutes." >&2
  exit 6
fi

/usr/bin/xcrun stapler staple "$pending_dmg"
/usr/bin/xcrun stapler validate "$pending_dmg"
rm -f "$final_dmg"
/bin/mv "$pending_dmg" "$final_dmg"
/usr/sbin/spctl --assess --type open --context context:primary-signature --verbose=2 "$final_dmg"
echo "$final_dmg"
