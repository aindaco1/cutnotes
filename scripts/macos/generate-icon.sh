#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source_image="${1:-$root_dir/assets/AppIconSource.png}"
output_icon="${2:-$root_dir/macos/Sources/CutNotesApp/Resources/AppIcon.icns}"
iconset_dir="$(mktemp -d)/AppIcon.iconset"
mkdir -p "$iconset_dir" "$(dirname "$output_icon")"

if [[ ! -f "$source_image" ]]; then
  echo "Missing icon source: $source_image" >&2
  exit 2
fi

make_icon() {
  local pixels="$1"
  local name="$2"
  /usr/bin/sips -s format png -z "$pixels" "$pixels" "$source_image" \
    --out "$iconset_dir/$name" >/dev/null
}

make_icon 16 icon_16x16.png
make_icon 32 icon_16x16@2x.png
make_icon 32 icon_32x32.png
make_icon 64 icon_32x32@2x.png
make_icon 128 icon_128x128.png
make_icon 256 icon_128x128@2x.png
make_icon 256 icon_256x256.png
make_icon 512 icon_256x256@2x.png
make_icon 512 icon_512x512.png
make_icon 1024 icon_512x512@2x.png

/usr/bin/iconutil -c icns "$iconset_dir" -o "$output_icon"
/usr/bin/sips -g pixelWidth -g pixelHeight "$iconset_dir/icon_16x16.png" >/dev/null
echo "$output_icon"
