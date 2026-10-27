#!/bin/bash
# The dashboard (D204), at http://127.0.0.1:4000 while this window is open.
cd "$(dirname "$0")" || exit 1
export PATH="$HOME/.local/bin:$PATH"   # where uv's installer puts it
if ! command -v uv >/dev/null; then
  echo 'uv is not installed yet: double-click "1 ... Setup" first.'
  read -r -p "Press Enter to close " _
  exit 1
fi
uv run python -m wuwa_vision serve || { read -r -p "Press Enter to close " _; exit 1; }
