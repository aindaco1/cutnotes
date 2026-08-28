#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 || ! -f "$1" ]]; then
  echo "usage: $0 /absolute/path/to/CutNotes-version-arm64.dmg" >&2
  exit 2
fi

dmg="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
mount_root="$(mktemp -d)"
mount_point="$mount_root/CutNotes"
trap 'hdiutil detach "$mount_point" >/dev/null 2>&1 || true; rm -rf "$mount_root"' EXIT

/usr/bin/codesign --verify --verbose=2 "$dmg"
/usr/bin/xcrun stapler validate "$dmg"
/usr/sbin/spctl --assess --type open --context context:primary-signature --verbose=2 "$dmg"
mkdir -p "$mount_point"
/usr/bin/hdiutil attach -readonly -nobrowse -mountpoint "$mount_point" "$dmg" >/dev/null
app="$mount_point/CutNotes.app"
/usr/bin/codesign --verify --deep --strict --verbose=2 "$app"
/usr/sbin/spctl --assess --type execute --verbose=2 "$app"
[[ "$(/usr/bin/file -b "$app/Contents/MacOS/CutNotes")" == *arm64* ]]
[[ ! -d "$app/Contents/Resources/Models" ]]
"$app/Contents/Resources/CLI/bin/cutnotes" --version
"$app/Contents/Resources/CLI/bin/cutnotes" doctor --json >/dev/null
echo "Verified mounted release: $dmg"
