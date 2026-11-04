#!/usr/bin/env bash
set -euo pipefail

version="8.1.1"
archive_sha256="b6863adde98898f42602017462871b5f6333e65aec803fdd7a6308639c52edf3"
cache_root="${CUTNOTES_RUNTIME_BUILD_ROOT:-$(getconf DARWIN_USER_CACHE_DIR)com.dustwave.cutnotes/runtime-build}"
prefix="${1:-$cache_root/ffmpeg-$version-arm64}"
source_cache="$cache_root/sources"
archive="$source_cache/ffmpeg-$version.tar.xz"
source_dir="$source_cache/ffmpeg-$version"

if [[ "$(uname -m)" != "arm64" ]]; then
  echo "CutNotes release runtimes are built on Apple Silicon." >&2
  exit 3
fi

if [[ -x "$prefix/bin/ffmpeg" && -x "$prefix/bin/ffprobe" ]]; then
  version_line="$("$prefix/bin/ffmpeg" -version 2>&1 | /usr/bin/sed -n '1p')"
  license_text="$("$prefix/bin/ffmpeg" -L 2>&1)"
  if [[ "$version_line" == *"ffmpeg version $version"* ]] \
    && [[ "$license_text" == *"Lesser General Public"* ]] \
    && [[ "$license_text" != *"terms of the GNU General Public"* ]]; then
    echo "$prefix"
    exit 0
  fi
fi

mkdir -p "$source_cache" "$(dirname "$prefix")"
github_revision="150ba6ddfabb5c433bb2fb3ee546d2a96e59066d"
github_sha256="10fd159e9fa6c89b2e9d3e0cf93df4bcfebe475061b563cd6f2af88e74c2ff52"
github_archive="$source_cache/ffmpeg-$version-github.tar.gz"
if [[ ! -f "$archive" ]] || ! echo "$archive_sha256  $archive" | /usr/bin/shasum -a 256 -c - >/dev/null 2>&1; then
  temporary_archive="$(mktemp "$source_cache/.ffmpeg-$version.XXXXXX.tar.xz")"
  trap 'rm -f "$temporary_archive"' EXIT
  if /usr/bin/curl --fail --location --silent --show-error --retry 1 --connect-timeout 20 --max-time 120 \
      "https://ffmpeg.org/releases/ffmpeg-$version.tar.xz" --output "$temporary_archive" \
      && echo "$archive_sha256  $temporary_archive" | /usr/bin/shasum -a 256 -c - >&2; then
    /bin/mv "$temporary_archive" "$archive"
  else
    /bin/rm -f "$temporary_archive"
    # The official FFmpeg mirror at the same release tag; independently pinned.
    if [[ ! -f "$github_archive" ]] || ! echo "$github_sha256  $github_archive" | /usr/bin/shasum -a 256 -c - >/dev/null 2>&1; then
      /usr/bin/curl --fail --location --silent --show-error --retry 2 --connect-timeout 20 --max-time 120 \
        "https://github.com/FFmpeg/FFmpeg/archive/$github_revision.tar.gz" --output "$temporary_archive"
      echo "$github_sha256  $temporary_archive" | /usr/bin/shasum -a 256 -c - >&2
      /bin/mv "$temporary_archive" "$github_archive"
    fi
  fi
  trap - EXIT
fi

rm -rf "$source_dir"
if [[ -f "$archive" ]] && echo "$archive_sha256  $archive" | /usr/bin/shasum -a 256 -c - >/dev/null 2>&1; then
  /usr/bin/tar -xJf "$archive" -C "$source_cache"
else
  mkdir -p "$source_dir"
  /usr/bin/tar -xzf "$github_archive" --strip-components 1 -C "$source_dir"
fi
build_dir="$(mktemp -d "$cache_root/.ffmpeg-build.XXXXXX")"
trap 'rm -rf "$build_dir"' EXIT

cd "$build_dir"
"$source_dir/configure" \
  --prefix="$prefix" \
  --arch=arm64 \
  --target-os=darwin \
  --cc=clang \
  --disable-static \
  --enable-shared \
  --disable-doc \
  --disable-debug \
  --disable-ffplay \
  --disable-network \
  --disable-autodetect \
  --enable-avfoundation \
  --enable-audiotoolbox \
  --enable-videotoolbox \
  --enable-neon \
  --enable-pic >&2
/usr/bin/make -j"$(sysctl -n hw.logicalcpu)" >&2
rm -rf "$prefix"
/usr/bin/make install >&2
/bin/cp "$source_dir/LICENSE.md" "$prefix/LICENSE.md"
/bin/cp "$source_dir/COPYING.LGPLv2.1" "$prefix/COPYING.LGPLv2.1"

version_line="$("$prefix/bin/ffmpeg" -version 2>&1 | /usr/bin/sed -n '1p')"
license_text="$("$prefix/bin/ffmpeg" -L 2>&1)"
[[ "$version_line" == *"ffmpeg version $version"* ]]
[[ "$license_text" == *"Lesser General Public"* ]]
if [[ "$license_text" == *"terms of the GNU General Public"* ]]; then
  echo "The CutNotes FFmpeg runtime unexpectedly enabled GPL components." >&2
  exit 4
fi
if find "$prefix/bin" "$prefix/lib" -type f -print0 \
  | xargs -0 /usr/bin/otool -L 2>/dev/null \
  | /usr/bin/grep '/opt/homebrew' >/dev/null; then
  echo "The CutNotes FFmpeg runtime unexpectedly linked Homebrew libraries." >&2
  exit 4
fi
echo "$prefix"
