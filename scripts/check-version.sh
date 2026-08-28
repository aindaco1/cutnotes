#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
expected="${1:-}"
python_version="$(cd "$root_dir" && python3 -c 'from cutnotes_core import VERSION; print(VERSION)')"
plist_version="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$root_dir/macos/Sources/CutNotesApp/Info.plist")"
local_version="$(/usr/bin/sed -n 's/^private let version = "\([^"]*\)"/\1/p' "$root_dir/macos/Sources/CutNotesLocal/main.swift")"

if [[ -z "$expected" ]]; then
  expected="$python_version"
fi
if [[ "$expected" != "$python_version" || "$expected" != "$plist_version" || "$expected" != "$local_version" ]]; then
  echo "Version mismatch: expected=$expected cli=$python_version app=$plist_version local=$local_version" >&2
  exit 3
fi
echo "$expected"
