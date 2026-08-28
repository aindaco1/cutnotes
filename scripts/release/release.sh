#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
version="$("$root_dir/scripts/check-version.sh" "${1:-}")"
dist_dir="$root_dir/dist"

cd "$root_dir"
python3 -m unittest discover -s tests -v
swift test --package-path macos
dmg="$("$root_dir/scripts/release/package-dmg.sh" "$version")"
"$root_dir/scripts/release/verify-release.sh" "$dmg"
appcast="$("$root_dir/scripts/release/generate-appcast.sh" "$version")"
(
  cd "$dist_dir"
  /usr/bin/shasum -a 256 "$(basename "$dmg")" "$(basename "$appcast")" > SHA256SUMS
)
echo "Release candidate ready in $dist_dir"
