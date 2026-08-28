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

python_version="$($python_framework_source/Versions/3.14/bin/python3 -c 'import platform; print(platform.python_version())')"
ffmpeg_version="$($ffmpeg_source -version | /usr/bin/awk 'NR == 1 {print $3}')"
if [[ "$python_version" != "3.14.6" || "$ffmpeg_version" != "8.1.1" ]]; then
  echo "Runtime lock mismatch: expected Python 3.14.6 and FFmpeg 8.1.1" >&2
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
/bin/cp -L "$ffmpeg_source" "$runtime_dir/bin/ffmpeg"
/bin/cp -L "$ffprobe_source" "$runtime_dir/bin/ffprobe"
/bin/chmod 0755 "$runtime_dir/bin/ffmpeg" "$runtime_dir/bin/ffprobe"

find "$runtime_dir/Python.framework" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$runtime_dir/Python.framework" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
rm -f "$runtime_dir/Python.framework/Versions/3.14/lib/python3.14/site-packages"
mkdir -p "$runtime_dir/Python.framework/Versions/3.14/lib/python3.14/site-packages"

dependency_list="$(mktemp)"
new_dependencies=1
while [[ "$new_dependencies" -gt 0 ]]; do
  : > "$dependency_list"
  while IFS= read -r candidate; do
    if /usr/bin/file -b "$candidate" | /usr/bin/grep -q 'Mach-O'; then
      /usr/bin/otool -L "$candidate" \
        | /usr/bin/awk '/^[[:space:]]*\// && $1 !~ /:$/ && $1 !~ /^\/System\/Library\// && $1 !~ /^\/usr\/lib\// {print $1}' \
        >> "$dependency_list"
    fi
  done < <(find "$runtime_dir" -type f -print)
  /usr/bin/sort -u "$dependency_list" -o "$dependency_list"
  new_dependencies=0
  while IFS= read -r dependency; do
    [[ -n "$dependency" ]] || continue
    if [[ "$dependency" == *"/Python.framework/Versions/3.14/Python" ]]; then
      continue
    fi
    destination="$runtime_dir/lib/$(basename "$dependency")"
    if [[ ! -f "$destination" ]]; then
      /bin/cp -L "$dependency" "$destination"
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
      replacement="@rpath/Python"
    else
      replacement="@rpath/$(basename "$dependency")"
    fi
    /usr/bin/install_name_tool -change "$dependency" "$replacement" "$candidate"
  done < <(
    /usr/bin/otool -L "$candidate" \
      | /usr/bin/awk '/^[[:space:]]*\// && $1 !~ /:$/ && $1 !~ /^\/System\/Library\// && $1 !~ /^\/usr\/lib\// {print $1}'
  )
  if [[ "$candidate" == "$runtime_dir/lib/"* ]]; then
    /usr/bin/install_name_tool -id "@rpath/$(basename "$candidate")" "$candidate" 2>/dev/null || true
  fi
done < <(find "$runtime_dir" -type f -print)

python_binary="$runtime_dir/Python.framework/Versions/3.14/bin/python3.14"
python_library="$runtime_dir/Python.framework/Versions/3.14/Python"
python_app_binary="$runtime_dir/Python.framework/Versions/3.14/Resources/Python.app/Contents/MacOS/Python"
/usr/bin/install_name_tool -id '@rpath/Python' "$python_library"
/usr/bin/install_name_tool -add_rpath '@executable_path/..' "$python_binary" 2>/dev/null || true
/usr/bin/install_name_tool -add_rpath '@executable_path/../../../../lib' "$python_binary" 2>/dev/null || true
/usr/bin/install_name_tool -add_rpath '@executable_path/../../../..' "$python_app_binary" 2>/dev/null || true
/usr/bin/install_name_tool -add_rpath '@executable_path/../../../../../../../lib' "$python_app_binary" 2>/dev/null || true
/usr/bin/install_name_tool -add_rpath '@executable_path/../lib' "$runtime_dir/bin/ffmpeg" 2>/dev/null || true
/usr/bin/install_name_tool -add_rpath '@executable_path/../lib' "$runtime_dir/bin/ffprobe" 2>/dev/null || true

# Apple Silicon requires every modified Mach-O to carry at least an ad-hoc
# signature before the runtime can execute its own verification probes.
while IFS= read -r candidate; do
  if /usr/bin/file -b "$candidate" | /usr/bin/grep -q 'Mach-O'; then
    /usr/bin/codesign --force --sign - --timestamp=none "$candidate"
  fi
done < <(find "$runtime_dir" -type f -print)

if find "$runtime_dir" -type f -print0 | xargs -0 /usr/bin/otool -L 2>/dev/null \
  | /usr/bin/awk '/^[[:space:]]*\// && $1 !~ /:$/ && $1 !~ /^\/System\/Library\// && $1 !~ /^\/usr\/lib\// {found=1} END {exit !found}'; then
  echo "Bundled runtime still contains non-system absolute load paths" >&2
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

PYTHONDONTWRITEBYTECODE=1 "$python_binary" -c 'import json, ssl, urllib.request; print(json.dumps({"python": "ready", "ssl": ssl.OPENSSL_VERSION.split()[0]}))' >/dev/null
"$runtime_dir/bin/ffmpeg" -version >/dev/null
"$runtime_dir/bin/ffprobe" -version >/dev/null
find "$runtime_dir/Python.framework" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$runtime_dir/Python.framework" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
