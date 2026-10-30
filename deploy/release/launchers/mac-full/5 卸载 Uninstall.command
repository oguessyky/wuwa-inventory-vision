#!/bin/bash
# Uninstall (D232): the shortcuts, the installed environment, the model and the program's files;
# it asks before your scans and settings. Runs from a copy, outside this folder.
if [ "$1" != "--copy" ]; then
  copy="${TMPDIR:-/tmp}/wuwa-uninstall.command"
  cp "$0" "$copy" && exec bash "$copy" --copy "$(cd "$(dirname "$0")" && pwd)"
fi
cd "${TMPDIR:-/tmp}" || exit 1
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null; then
  echo 'uv is not installed: nothing was set up here, so deleting this folder removes it all.'
  read -r -p "Press Enter to close " _
  exit 1
fi
uv run --project "$2" python -m wuwa_vision uninstall --folder "$2"
