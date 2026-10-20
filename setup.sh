#!/usr/bin/env bash
# Set the project up on macOS or Linux (D70): checks the two prerequisites, then
# hands over to tools/setup.py, which works out what this machine is.
#
#   ./setup.sh          # ask before each step
#   ./setup.sh --yes
#   ./setup.sh --scanner   # this machine scans for a home: the home sends the catalogue
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null; then
  echo "Python 3.12 is missing: brew install python@3.12"
  exit 1
fi
if ! command -v uv >/dev/null; then
  echo "uv is missing. Installing it..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

exec python3 tools/setup.py "$@"
