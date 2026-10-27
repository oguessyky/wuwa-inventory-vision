#!/bin/bash
# Scan the bag (D204): then click into the game. Ctrl+C in this window stops it (a Mac has
# no F9: that would need the Accessibility permission). Allow Screen Recording when asked.
cd "$(dirname "$0")" || exit 1
export PATH="$HOME/.local/bin:$PATH"   # where uv's installer puts it
if ! command -v uv >/dev/null; then
  echo 'uv is not installed yet: double-click "1 ... Setup" first.'
  read -r -p "Press Enter to close " _
  exit 1
fi
uv run python -m wuwa_vision live --identify || { read -r -p "Press Enter to close " _; exit 1; }
