#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 /absolute/path/to/CutNotes.app" >&2
  exit 2
fi

app_bundle="$1"
root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
licenses_dir="$app_bundle/Contents/Resources/Licenses"
package_checkouts="${CUTNOTES_SWIFT_SCRATCH:-$root_dir/macos/.build}/checkouts"

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

copy_license "$root_dir/shared/dust-wave-platform/native/LICENSE.Record" "Record-MIT.txt"
copy_license "$root_dir/shared/dust-wave-platform/LICENSE" "DustWavePlatform-MIT.txt"
for source in "$root_dir"/shared/dust-wave-platform/{desktop,support}/LICENSE.*; do
  copy_license "$source" "$(basename "$source")"
done
copy_license "$package_checkouts/FluidAudio/LICENSE" "FluidAudio-Apache-2.0.txt"
copy_license "$package_checkouts/Sparkle/LICENSE" "Sparkle-MIT-and-external.txt"
copy_license "$root_dir/third_party/SQLite-Public-Domain.txt" "SQLite-Public-Domain.txt"

python_license="${CUTNOTES_PYTHON_FRAMEWORK:-/opt/homebrew/opt/python@3.14/Frameworks/Python.framework}/Versions/3.14/lib/python3.14/LICENSE.txt"
copy_license "$python_license" "Python-PSF.txt"

ffmpeg_prefix="${CUTNOTES_FFMPEG_PREFIX:-$(cd "$(dirname "${CUTNOTES_FFMPEG_SOURCE:-/opt/homebrew/bin/ffmpeg}")/.." && pwd)}"
copy_license "$ffmpeg_prefix/LICENSE.md" "FFmpeg-LICENSE.md"
copy_license "$ffmpeg_prefix/COPYING.LGPLv2.1" "FFmpeg-LGPL-2.1.txt"

copy_license "$(dirname "$CUTNOTES_PYTHON_FRAMEWORK")/Python-Distribution-Licenses.rtf" "Python-Distribution-Licenses.rtf"
