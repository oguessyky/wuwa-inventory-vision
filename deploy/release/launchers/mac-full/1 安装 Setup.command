#!/bin/bash
# Set it up, once (D204): the same as setup.ps1 on Windows. macOS may ask, the first time,
# whether to open a file from the internet: right-click it and choose Open.
cd "$(dirname "$0")" || exit 1
export PATH="$HOME/.local/bin:$PATH"   # where uv's installer puts it
./setup.sh
read -r -p "Press Enter to close " _
