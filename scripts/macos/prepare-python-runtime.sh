#!/usr/bin/env bash
set -euo pipefail
# Extract the signed PSF runtime; never install or modify the host's Python.
version=3.14.8
sha256=507fc086c5c006ff875d344a75b4e67b8fb3c401f1bc4908c6250adb673d4907
cache_root="${CUTNOTES_RUNTIME_BUILD_ROOT:-$(getconf DARWIN_USER_CACHE_DIR)com.dustwave.cutnotes/runtime-build}"
archive="$cache_root/python-$version-macos11.pkg"
output="$cache_root/python-$version-official"
mkdir -p "$cache_root"
if [[ -d "$output/Python.framework" && -f "$output/verified-$sha256" ]]; then
  echo "$output/Python.framework"
  exit 0
fi
if [[ ! -f "$archive" ]] || ! echo "$sha256  $archive" | shasum -a 256 -c - >/dev/null 2>&1; then
  curl --fail --location --silent --show-error --retry 2 --connect-timeout 20 --max-time 180 \
    "https://www.python.org/ftp/python/$version/python-$version-macos11.pkg" -o "$archive"
fi
echo "$sha256  $archive" | shasum -a 256 -c - >&2
/usr/sbin/pkgutil --check-signature "$archive" | grep -F 'Python Software Foundation (BMM5U3QVKW)' >&2
stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
/usr/sbin/pkgutil --expand-full "$archive" "$stage/extracted"
mkdir -p "$output"
/usr/bin/ditto --norsrc --noextattr "$stage/extracted/Python_Framework.pkg/Payload" "$output/Python.framework"
/bin/cp "$stage/extracted/Resources/License.rtf" "$output/Python-Distribution-Licenses.rtf"
touch "$output/verified-$sha256"
echo "$output/Python.framework"
