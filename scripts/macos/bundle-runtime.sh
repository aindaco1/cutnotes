#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 /absolute/path/to/CutNotes.app" >&2
  exit 2
fi

app_bundle="$1"
runtime_dir="$app_bundle/Contents/Resources/Runtime"
python_framework_source="${CUTNOTES_PYTHON_FRAMEWORK:-/opt/homebrew/opt/python@3.14/Frameworks/Python.framework}"
ffmpeg_source="${CUTNOTES_FFMPEG_SOURCE:-/opt/homebrew/bin/ffmpeg}"
ffprobe_source="${CUTNOTES_FFPROBE_SOURCE:-/opt/homebrew/bin/ffprobe}"

if [[ "$app_bundle" != /* || ! -d "$app_bundle/Contents" ]]; then
  echo "App bundle must be an existing absolute .app path" >&2
  exit 2
fi
if [[ ! -d "$python_framework_source" || ! -x "$ffmpeg_source" || ! -x "$ffprobe_source" ]]; then
  echo "Pinned Python, FFmpeg, or FFprobe source is unavailable" >&2
  exit 3
fi

python_version="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$python_framework_source/Versions/3.14/Resources/Info.plist")"
ffmpeg_version="$($ffmpeg_source -version | /usr/bin/awk 'NR == 1 {print $3}')"
if [[ "$python_version" != "3.14.8" || "$ffmpeg_version" != "8.1.1" ]]; then
  echo "Runtime lock mismatch: expected Python 3.14.8 and FFmpeg 8.1.1" >&2
  exit 3
fi
ffmpeg_license_text="$("$ffmpeg_source" -L 2>&1)"
if [[ "$ffmpeg_license_text" != *"Lesser General Public"* ]] \
  || [[ "$ffmpeg_license_text" == *"terms of the GNU General Public"* ]]; then
  echo "The bundled FFmpeg runtime must be the CutNotes LGPL build without GPL components" >&2
  exit 3
fi

rm -rf "$runtime_dir"
mkdir -p "$runtime_dir/bin" "$runtime_dir/lib"
/usr/bin/ditto --norsrc --noextattr "$python_framework_source" "$runtime_dir/Python.framework"
# Recent Homebrew bottles omit the framework's public symlinks. Restore the
# canonical versioned layout before signing the independently bundled copy.
/bin/ln -sfn 3.14 "$runtime_dir/Python.framework/Versions/Current"
/bin/ln -sfn Versions/Current/Python "$runtime_dir/Python.framework/Python"
/bin/ln -sfn Versions/Current/Resources "$runtime_dir/Python.framework/Resources"

/bin/cp -L "$ffmpeg_source" "$runtime_dir/bin/ffmpeg"
/bin/cp -L "$ffprobe_source" "$runtime_dir/bin/ffprobe"
/bin/chmod 0755 "$runtime_dir/bin/ffmpeg" "$runtime_dir/bin/ffprobe"
# A previously verified relocatable LGPL build may be supplied for local testing.
# Its sibling codec libraries are already @rpath-relative, so otool's absolute
# dependency traversal below cannot discover them.
ffmpeg_sibling_lib="$(dirname "$ffmpeg_source")/../lib"
if [[ -d "$ffmpeg_sibling_lib" ]]; then
  for library in "$ffmpeg_sibling_lib"/libav*.dylib "$ffmpeg_sibling_lib"/libsw*.dylib; do
    [[ -f "$library" ]] || continue
    /bin/cp -L "$library" "$runtime_dir/lib/$(basename "$library")"
  done
fi


find "$runtime_dir/Python.framework" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$runtime_dir/Python.framework" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
rm -rf "$runtime_dir/Python.framework/Versions/3.14/lib/python3.14/site-packages"
# CutNotes does not use Tk/IDLE. Keep the bundled runtime independent of GUI
# Python frameworks and their separate installation layout.
rm -rf "$runtime_dir/Python.framework/Versions/3.14/Frameworks"
rm -f "$runtime_dir/Python.framework/Versions/3.14/lib/python3.14/lib-dynload/"_tkinter*.so
# PSF includes this link-time development object. It is never used to run
# Python, cannot carry a distributable executable signature, and fails notary.
rm -f "$runtime_dir/Python.framework/Versions/3.14/lib/python3.14/config-3.14-darwin/python.o"
mkdir -p "$runtime_dir/Python.framework/Versions/3.14/lib/python3.14/site-packages"

# Install only the reviewed, hash-pinned macOS 15 wheels. Never resolve dependencies
# while the application runs; all inference libraries and TLS roots ship here.
root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
python3 -m pip install \
  --only-binary=:all: --require-hashes --no-deps --no-compile \
  --platform macosx_15_0_arm64 --python-version 3.14 --implementation cp --abi cp314 \
  --target "$runtime_dir/Python.framework/Versions/3.14/lib/python3.14/site-packages" \
  -r "$root_dir/config/gemma-runtime-requirements.txt"

dependency_list="$(mktemp)"
new_dependencies=1
while [[ "$new_dependencies" -gt 0 ]]; do
  : > "$dependency_list"
  while IFS= read -r candidate; do
    if /usr/bin/file -b "$candidate" | /usr/bin/grep -q 'Mach-O'; then
      /usr/bin/otool -L "$candidate" \
        | /usr/bin/awk '/^[[:space:]]+\// && $1 !~ /:$/ && $1 !~ /^\/System\/Library\// && $1 !~ /^\/usr\/lib\// {print $1}' \
        >> "$dependency_list"
    fi
  done < <(python3 "$root_dir/scripts/macos/macho-files.py" "$runtime_dir")
  /usr/bin/sort -u "$dependency_list" -o "$dependency_list"
  new_dependencies=0
  while IFS= read -r dependency; do
    [[ -n "$dependency" ]] || continue
    if [[ "$dependency" == *"/Python.framework/Versions/3.14/Python" ]]; then
      continue
    fi
    destination="$runtime_dir/lib/$(basename "$dependency")"
    if [[ ! -f "$destination" ]]; then
      dependency_source="$dependency"
      if [[ "$dependency" == /Library/Frameworks/Python.framework/* ]]; then
        dependency_source="$python_framework_source/${dependency#/Library/Frameworks/Python.framework/}"
      fi
      /bin/cp -L "$dependency_source" "$destination"
      /bin/chmod u+w "$destination"
      new_dependencies=$((new_dependencies + 1))
    fi
  done < "$dependency_list"
done
/bin/rm -f "$dependency_list"

while IFS= read -r candidate; do
  if ! /usr/bin/file -b "$candidate" | /usr/bin/grep -q 'Mach-O'; then
    continue
  fi
  /usr/bin/codesign --remove-signature "$candidate" 2>/dev/null || true
  while IFS= read -r dependency; do
    [[ -n "$dependency" ]] || continue
    if [[ "$dependency" == *"/Python.framework/Versions/3.14/Python" ]]; then
      dependency_target="$runtime_dir/Python.framework/Versions/3.14/Python"
    else
      dependency_target="$runtime_dir/lib/$(basename "$dependency")"
    fi
    replacement="@loader_path/$(python3 -c 'import os,sys; print(os.path.relpath(sys.argv[1], os.path.dirname(sys.argv[2])))' "$dependency_target" "$candidate")"
    /usr/bin/install_name_tool -change "$dependency" "$replacement" "$candidate"
  done < <(
    /usr/bin/otool -L "$candidate" \
      | /usr/bin/awk '/^[[:space:]]+\// && $1 !~ /:$/ && $1 !~ /^\/System\/Library\// && $1 !~ /^\/usr\/lib\// {print $1}'
  )
  if [[ "$candidate" == *.dylib || "$candidate" == *.so ]]; then
    /usr/bin/install_name_tool -id "@rpath/$(basename "$candidate")" "$candidate" 2>/dev/null || true
  fi
done < <(python3 "$root_dir/scripts/macos/macho-files.py" "$runtime_dir")

python_binary="$runtime_dir/Python.framework/Versions/3.14/bin/python3.14"
python_library="$runtime_dir/Python.framework/Versions/3.14/Python"
python_app_binary="$runtime_dir/Python.framework/Versions/3.14/Resources/Python.app/Contents/MacOS/Python"
/usr/bin/install_name_tool -id '@rpath/Python' "$python_library"

# Apple Silicon requires every modified Mach-O to carry at least an ad-hoc
# signature before the runtime can execute its own verification probes.
while IFS= read -r candidate; do
  if /usr/bin/file -b "$candidate" | /usr/bin/grep -q 'Mach-O'; then
    /usr/bin/codesign --force --sign - --timestamp=none "$candidate"
  fi
done < <(python3 "$root_dir/scripts/macos/macho-files.py" "$runtime_dir")

if python3 "$root_dir/scripts/macos/macho-files.py" "$runtime_dir" | while IFS= read -r candidate; do /usr/bin/otool -L "$candidate"; done 2>/dev/null \
  | /usr/bin/awk '/^[[:space:]]+\// && $1 !~ /:$/ && $1 !~ /^\/System\/Library\// && $1 !~ /^\/usr\/lib\// {found=1} END {exit !found}'; then
  echo "Bundled runtime still contains non-system absolute load paths" >&2
  while IFS= read -r candidate; do
    /usr/bin/otool -L "$candidate" | /usr/bin/awk '/^[[:space:]]+\// && $1 !~ /:$/ && $1 !~ /^\/System\/Library\// && $1 !~ /^\/usr\/lib\// {print FILENAME, $0}' >&2
  done < <(python3 "$root_dir/scripts/macos/macho-files.py" "$runtime_dir")
  exit 4
fi

manifest="$runtime_dir/runtime-manifest.json"
/usr/bin/plutil -create xml1 "$manifest"
/usr/bin/plutil -insert schema -string cutnotes-runtime-v1 "$manifest"
/usr/bin/plutil -insert architecture -string arm64 "$manifest"
/usr/bin/plutil -insert python_version -string "$python_version" "$manifest"
/usr/bin/plutil -insert ffmpeg_version -string "$ffmpeg_version" "$manifest"
/usr/bin/plutil -insert ffmpeg_license -string LGPL-2.1-or-later "$manifest"
/usr/bin/plutil -convert json "$manifest"

PYTHONDONTWRITEBYTECODE=1 "$python_binary" -c 'import json, ssl, urllib.request, mlx.core, mlx_lm, transformers; print(json.dumps({"python": "ready", "ssl": ssl.OPENSSL_VERSION.split()[0]}))' >/dev/null
"$runtime_dir/bin/ffmpeg" -version >/dev/null
"$runtime_dir/bin/ffprobe" -version >/dev/null
find "$runtime_dir/Python.framework" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$runtime_dir/Python.framework" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
