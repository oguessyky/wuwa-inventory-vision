#!/bin/bash
# Update to the home's version, only when the home says this one is behind (D203, D204).
# Runs from a copy: a script rewritten while it runs would go wrong.
if [ "$1" != "--copy" ]; then
  copy="${TMPDIR:-/tmp}/wuwa-update.command"
  cp "$0" "$copy" && exec bash "$copy" --copy "$(cd "$(dirname "$0")" && pwd)"
fi
cd "$2" || exit 1
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null; then
  echo 'uv is not installed yet: double-click "1 ... Setup" first.'
  read -r -p "Press Enter to close " _
  exit 1
fi
uv run python -m wuwa_vision update
case $? in
  0) ./setup.sh --scanner --yes ;;   # updated: set it up again
  3) ;;                          # nothing to update
  *) read -r -p "Press Enter to close " _; exit 1 ;;
esac
read -r -p "Press Enter to close " _
