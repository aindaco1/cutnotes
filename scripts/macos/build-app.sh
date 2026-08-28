#!/usr/bin/env bash
set -euo pipefail

configuration="${1:-debug}"
if [[ "$configuration" != "debug" && "$configuration" != "release" ]]; then
  echo "usage: $0 [debug|release]" >&2
  exit 2
fi

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
package_dir="$root_dir/macos"
dist_dir="$root_dir/dist"
cache_root="${CUTNOTES_BUILD_CACHE:-$(getconf DARWIN_USER_CACHE_DIR)com.dustwave.cutnotes/build}"
final_app_bundle="$cache_root/CutNotes.app"
app_link="$dist_dir/CutNotes.app"
stage_dir="$(mktemp -d)"
trap 'rm -rf "$stage_dir"' EXIT
app_bundle="$stage_dir/CutNotes.app"
contents="$app_bundle/Contents"
macos_dir="$contents/MacOS"
resources_dir="$contents/Resources"
frameworks_dir="$contents/Frameworks"
helpers_dir="$resources_dir/Helpers"
cli_dir="$resources_dir/CLI"

if [[ -z "${CUTNOTES_FFMPEG_SOURCE:-}" || -z "${CUTNOTES_FFPROBE_SOURCE:-}" ]]; then
  ffmpeg_prefix="$(
    "$root_dir/scripts/macos/build-ffmpeg-runtime.sh" | /usr/bin/tail -n 1
  )"
  export CUTNOTES_FFMPEG_SOURCE="$ffmpeg_prefix/bin/ffmpeg"
  export CUTNOTES_FFPROBE_SOURCE="$ffmpeg_prefix/bin/ffprobe"
  export CUTNOTES_FFMPEG_PREFIX="$ffmpeg_prefix"
fi

swift build --package-path "$package_dir" -c "$configuration" --arch arm64 --product CutNotes
swift build --package-path "$package_dir" -c "$configuration" --arch arm64 --product CutNotesLocal
bin_dir="$(swift build --package-path "$package_dir" -c "$configuration" --arch arm64 --show-bin-path)"

rm -rf "$app_bundle"
mkdir -p "$macos_dir" "$resources_dir" "$frameworks_dir" "$helpers_dir" "$cli_dir/bin"
/bin/cp "$bin_dir/CutNotes" "$macos_dir/CutNotes"
/bin/cp "$bin_dir/CutNotesLocal" "$helpers_dir/CutNotesLocal"
/bin/chmod 0755 "$macos_dir/CutNotes" "$helpers_dir/CutNotesLocal"
/bin/cp "$package_dir/Sources/CutNotesApp/Info.plist" "$contents/Info.plist"

if [[ -d "$bin_dir/CutNotes_CutNotesApp.bundle" ]]; then
  /usr/bin/ditto "$bin_dir/CutNotes_CutNotesApp.bundle" "$resources_dir/CutNotes_CutNotesApp.bundle"
fi
if [[ ! -d "$bin_dir/Sparkle.framework" ]]; then
  echo "Sparkle.framework was not produced by SwiftPM" >&2
  exit 3
fi
/usr/bin/ditto "$bin_dir/Sparkle.framework" "$frameworks_dir/Sparkle.framework"

/bin/cp "$root_dir/cutnotes" "$cli_dir/cutnotes"
/usr/bin/ditto "$root_dir/cutnotes_core" "$cli_dir/cutnotes_core"
/usr/bin/find "$cli_dir/cutnotes_core" -type d -name __pycache__ -prune -exec /bin/rm -rf {} +
/usr/bin/find "$cli_dir/cutnotes_core" -type f -name '*.py[co]' -delete
/bin/cp "$root_dir/scripts/macos/cutnotes-launcher" "$cli_dir/bin/cutnotes"
/bin/chmod 0755 "$cli_dir/bin/cutnotes" "$cli_dir/cutnotes"

"$root_dir/scripts/macos/generate-icon.sh" \
  "$root_dir/assets/AppIconSource.png" "$resources_dir/AppIcon.icns" >/dev/null
"$root_dir/scripts/macos/bundle-runtime.sh" "$app_bundle"
"$root_dir/scripts/macos/bundle-licenses.sh" "$app_bundle"

public_key_file="$root_dir/config/sparkle-public-key.txt"
public_key="${CUTNOTES_SPARKLE_PUBLIC_KEY:-}"
if [[ -z "$public_key" && -f "$public_key_file" ]]; then
  public_key="$(tr -d '[:space:]' < "$public_key_file")"
fi
if [[ -n "$public_key" ]]; then
  /usr/libexec/PlistBuddy -c "Set :SUPublicEDKey $public_key" "$contents/Info.plist"
elif [[ "$configuration" == "release" ]]; then
  echo "A dedicated Sparkle public key is required for release builds" >&2
  exit 3
fi

"$root_dir/scripts/macos/sign-app.sh" "$app_bundle"

/usr/bin/plutil -lint "$contents/Info.plist"
/usr/bin/file "$macos_dir/CutNotes" "$helpers_dir/CutNotesLocal" "$resources_dir/Runtime/bin/ffmpeg"
mkdir -p "$dist_dir" "$cache_root"
rm -rf "$final_app_bundle"
/usr/bin/ditto --norsrc --noextattr "$app_bundle" "$final_app_bundle"
/usr/bin/xattr -dr com.apple.FinderInfo "$final_app_bundle" 2>/dev/null || true
/usr/bin/xattr -dr com.apple.ResourceFork "$final_app_bundle" 2>/dev/null || true
/usr/bin/codesign --verify --deep --strict --verbose=2 "$final_app_bundle"
rm -rf "$app_link"
/bin/ln -s "$final_app_bundle" "$app_link"
echo "$app_link"
