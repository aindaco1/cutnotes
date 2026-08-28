#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
version="$("$root_dir/scripts/check-version.sh" "${1:-}")"
dist_dir="$root_dir/dist"
dmg="$dist_dir/CutNotes-$version-arm64.dmg"
sparkle_tool="$root_dir/macos/.build/artifacts/sparkle/Sparkle/bin/generate_appcast"
archive_dir="$(mktemp -d)"
trap 'rm -rf "$archive_dir"' EXIT

if [[ ! -f "$dmg" || ! -x "$sparkle_tool" ]]; then
  echo "A notarized DMG and the resolved Sparkle tools are required." >&2
  exit 3
fi
/bin/cp "$dmg" "$archive_dir/"
/bin/cp "$root_dir/CHANGELOG.md" "$archive_dir/CutNotes-$version-arm64.md"

arguments=(
  --download-url-prefix "https://github.com/aindaco1/cutnotes/releases/download/v$version/"
  --link "https://github.com/aindaco1/cutnotes"
  --embed-release-notes
  --maximum-versions 3
  -o "$dist_dir/appcast.xml"
)
if [[ -n "${CUTNOTES_SPARKLE_PRIVATE_KEY:-}" ]]; then
  printf '%s' "$CUTNOTES_SPARKLE_PRIVATE_KEY" \
    | "$sparkle_tool" --ed-key-file - "${arguments[@]}" "$archive_dir"
else
  "$sparkle_tool" --account com.dustwave.cutnotes "${arguments[@]}" "$archive_dir"
fi

/usr/bin/xmllint --noout "$dist_dir/appcast.xml"
if ! /usr/bin/grep -q 'sparkle:edSignature=' "$dist_dir/appcast.xml"; then
  echo "The generated appcast does not contain an EdDSA archive signature." >&2
  exit 4
fi
if ! /usr/bin/grep -Fq "CutNotes-$version-arm64.dmg" "$dist_dir/appcast.xml"; then
  echo "The generated appcast does not reference this release archive." >&2
  exit 4
fi
echo "$dist_dir/appcast.xml"
