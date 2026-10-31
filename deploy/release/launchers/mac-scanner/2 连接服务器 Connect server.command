#!/bin/bash
# Give this Mac its server, once (D145, D204): the address and key the server's setup gave.
cd "$(dirname "$0")" || exit 1
export PATH="$HOME/.local/bin:$PATH"   # where uv's installer puts it
if ! command -v uv >/dev/null; then
  echo 'uv is not installed yet: double-click "1 ... Setup" first.'
  read -r -p "Press Enter to close " _
  exit 1
fi
echo "The server's address: just its name on Tailscale (Enter tries wuwa-server), or the name"
echo "Tailscale shows (wuwa-server.your-tailnet.ts.net), or its 100.x address."
read -r -p "Server address [Enter = wuwa-server]: " server
echo "The key: press Enter to take server.key from your Downloads folder (download it from"
echo "the server's data folder on the NAS first), or paste the key, or drag the file in."
read -r -p "Server key [Enter = server.key in Downloads]: " key
uv run python -m wuwa_vision server set "$server" "$key"
read -r -p "Press Enter to close " _
