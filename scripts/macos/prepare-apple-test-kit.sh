#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 /path/to/CutNotes.app /new/test-kit-directory" >&2
  exit 2
fi

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
app_bundle="$1"
kit_dir="$2"
/usr/bin/codesign --verify --deep --strict "$app_bundle"
signature_details="$(/usr/bin/codesign -dvv "$app_bundle" 2>&1)"
if [[ "$signature_details" != *$'\nAuthority=Developer ID Application:'* ]]; then
  echo "The test kit requires a Developer ID signed app." >&2
  exit 3
fi
# Do not overwrite a previous kit or results.
/bin/mkdir "$kit_dir"
/usr/bin/ditto --norsrc --noextattr "$app_bundle" "$kit_dir/CutNotes.app"
/bin/mkdir -p "$kit_dir/scripts" "$kit_dir/tests/fixtures"
/bin/cp "$root_dir/scripts/check-apple-formatting.py" "$root_dir/scripts/apple_test_support.py" "$kit_dir/scripts/"
/bin/cp "$root_dir/scripts/macos/run-apple-test-kit.command" "$kit_dir/Run Apple checks.command"
/bin/chmod 0755 "$kit_dir/Run Apple checks.command"
/bin/cp "$root_dir/docs/APPLE_MODEL_TEST_KIT.md" "$kit_dir/README.md"
# The checker imports the exact packaged core, without a second implementation.
/bin/ln -s CutNotes.app/Contents/Resources/CLI/cutnotes_core "$kit_dir/cutnotes_core"

python_bin="$kit_dir/CutNotes.app/Contents/Resources/Runtime/Python.framework/Versions/3.14/bin/python3"
PYTHONDONTWRITEBYTECODE=1 "$python_bin" - "$root_dir" "$kit_dir" <<'PY'
import hashlib, json, pathlib, subprocess, sys
root, kit = map(pathlib.Path, sys.argv[1:])
fixtures, hashes = [], {}
for name in ("apple-formatting.json", "apple-formatting-holdout.json"):
    source = root / "tests/fixtures" / name
    fixtures.extend(json.loads(source.read_text()))
    hashes[name] = hashlib.sha256(source.read_bytes()).hexdigest()
(kit / "tests/fixtures/apple-formatting.json").write_text(json.dumps(fixtures, indent=2) + "\n")
manifest = {
    "schema_version": "cutnotes.apple.test-kit.v1",
    "source_commit": subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(),
    "source_dirty": bool(subprocess.check_output(["git", "-C", str(root), "status", "--porcelain"], text=True)),
    "fixtures_sha256": hashes,
    "cases": len(fixtures),
    "files_sha256": {str(p.relative_to(kit)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (
        kit / "scripts/check-apple-formatting.py", kit / "scripts/apple_test_support.py", kit / "Run Apple checks.command",
        kit / "CutNotes.app/Contents/Resources/Helpers/CutNotesLocal",
        kit / "cutnotes_core/providers.py", kit / "cutnotes_core/formatting.py")},
}
(kit / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
PY
/usr/bin/codesign --verify --deep --strict "$kit_dir/CutNotes.app"
echo "$kit_dir"
