#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 /absolute/path/to/CutNotes.app" >&2
  exit 2
fi

app_bundle="$1"
root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
licenses_dir="$app_bundle/Contents/Resources/Licenses"
package_checkouts="$root_dir/macos/.build/checkouts"

rm -rf "$licenses_dir"
mkdir -p "$licenses_dir"
/bin/cp "$root_dir/LICENSE" "$licenses_dir/CutNotes-MIT.txt"
/bin/cp "$root_dir/THIRD_PARTY_NOTICES.md" "$licenses_dir/THIRD_PARTY_NOTICES.md"

copy_license() {
  local source="$1"
  local destination="$2"
  if [[ ! -f "$source" ]]; then
    echo "Required license file is missing: $source" >&2
    exit 3
  fi
  /bin/cp "$source" "$licenses_dir/$destination"
}

copy_license "$package_checkouts/record/LICENSE" "Record-MIT.txt"
copy_license "$package_checkouts/FluidAudio/LICENSE" "FluidAudio-Apache-2.0.txt"
copy_license "$package_checkouts/Sparkle/LICENSE" "Sparkle-MIT-and-external.txt"
copy_license "$package_checkouts/swift-argument-parser/LICENSE.txt" "SwiftArgumentParser-Apache-2.0.txt"
copy_license "$root_dir/third_party/SQLite-Public-Domain.txt" "SQLite-Public-Domain.txt"

python_license="${CUTNOTES_PYTHON_FRAMEWORK:-/opt/homebrew/opt/python@3.14/Frameworks/Python.framework}/Versions/3.14/lib/python3.14/LICENSE.txt"
copy_license "$python_license" "Python-PSF.txt"

ffmpeg_prefix="${CUTNOTES_FFMPEG_PREFIX:-$(cd "$(dirname "${CUTNOTES_FFMPEG_SOURCE:-/opt/homebrew/bin/ffmpeg}")/.." && pwd)}"
copy_license "$ffmpeg_prefix/LICENSE.md" "FFmpeg-LICENSE.md"
copy_license "$ffmpeg_prefix/COPYING.LGPLv2.1" "FFmpeg-LGPL-2.1.txt"

for formula in openssl@3 xz mpdecimal zstd; do
  prefix="$(/opt/homebrew/bin/brew --prefix "$formula")"
  found=0
  while IFS= read -r source; do
    found=1
    name="$(basename "$source")"
    /bin/cp "$source" "$licenses_dir/${formula//\//-}-$name"
  done < <(find -L "$prefix" -maxdepth 1 -type f \( -iname 'LICENSE*' -o -iname 'COPYING*' -o -iname 'COPYRIGHT*' \) -print | sort)
  if [[ "$found" -eq 0 ]]; then
    echo "No license files found for Homebrew formula: $formula" >&2
    exit 3
  fi
done
