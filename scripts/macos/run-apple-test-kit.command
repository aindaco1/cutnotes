#!/bin/bash
set -euo pipefail

kit_dir="$(cd "$(dirname "$0")" && pwd)"
required_model=(--require-model "AFM 3 Core Advanced")
if [[ $# -eq 1 && "$1" == "--any-model" ]]; then
  required_model=()
elif [[ $# -ne 0 ]]; then
  echo "usage: $0 [--any-model]" >&2
  exit 2
fi

app_bundle="$kit_dir/CutNotes.app"
/usr/bin/codesign --verify --deep --strict "$app_bundle"
resources="$app_bundle/Contents/Resources"
results="$(/usr/bin/mktemp -d "$HOME/Desktop/CutNotes-Apple-Check.XXXXXX")"
echo "Results: $results/acceptance"
export PYTHONDONTWRITEBYTECODE=1
"$resources/Runtime/Python.framework/Versions/3.14/bin/python3" \
  "$kit_dir/scripts/check-apple-formatting.py" \
  --engine "$resources/Helpers/CutNotesLocal" \
  --output-dir "$results/acceptance" "${required_model[@]}"
