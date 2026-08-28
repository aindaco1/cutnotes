#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 /absolute/path/to/CutNotes.app" >&2
  exit 2
fi

app_bundle="$1"
identity="${CUTNOTES_SIGNING_IDENTITY:--}"
entitlements="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/macos/Sources/CutNotesApp/CutNotes.entitlements"
sign_options=(--force --sign "$identity")
if [[ "$identity" == "-" ]]; then
  sign_options+=(--timestamp=none)
else
  sign_options+=(--options runtime --timestamp)
fi

/usr/bin/xattr -cr "$app_bundle" 2>/dev/null || true

while IFS= read -r candidate; do
  if /usr/bin/file -b "$candidate" | /usr/bin/grep -q 'Mach-O'; then
    /usr/bin/xattr -c "$candidate" 2>/dev/null || true
    /usr/bin/codesign "${sign_options[@]}" "$candidate"
  fi
done < <(find "$app_bundle/Contents" -type f -print)

while IFS= read -r nested_bundle; do
  /usr/bin/xattr -c "$nested_bundle" 2>/dev/null || true
  /usr/bin/codesign "${sign_options[@]}" "$nested_bundle"
done < <(
  find "$app_bundle/Contents" -depth -type d \
    \( -name '*.xpc' -o -name '*.app' -o -name '*.framework' \) -print
)

/usr/bin/xattr -c "$app_bundle" 2>/dev/null || true
/usr/bin/codesign "${sign_options[@]}" --entitlements "$entitlements" "$app_bundle"
/usr/bin/codesign --verify --deep --strict --verbose=2 "$app_bundle"
