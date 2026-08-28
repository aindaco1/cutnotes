#!/usr/bin/env bash
set -euo pipefail

mode="${1:-run}"
app_name="CutNotes"
bundle_id="com.dustwave.cutnotes"
root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
app_bundle="$root_dir/dist/$app_name.app"
app_binary="$app_bundle/Contents/MacOS/$app_name"

pkill -x "$app_name" >/dev/null 2>&1 || true
"$root_dir/scripts/macos/build-app.sh" debug

open_app() {
  /usr/bin/open -n "$app_bundle"
}

case "$mode" in
  run)
    open_app
    ;;
  --debug|debug)
    lldb -- "$app_binary"
    ;;
  --logs|logs)
    open_app
    /usr/bin/log stream --info --style compact --predicate "process == \"$app_name\""
    ;;
  --telemetry|telemetry)
    open_app
    /usr/bin/log stream --info --style compact --predicate "subsystem == \"$bundle_id\""
    ;;
  --verify|verify)
    open_app
    sleep 2
    pgrep -x "$app_name" >/dev/null
    ;;
  *)
    echo "usage: $0 [run|--debug|--logs|--telemetry|--verify]" >&2
    exit 2
    ;;
esac
