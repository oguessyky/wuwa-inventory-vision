#!/bin/bash
# Give this Mac its home, once (D145, D204): the address and key the home's setup gave.
cd "$(dirname "$0")" || exit 1
export PATH="$HOME/.local/bin:$PATH"   # where uv's installer puts it
if ! command -v uv >/dev/null; then
  echo 'uv is not installed yet: double-click "1 ... Setup" first.'
  read -r -p "Press Enter to close " _
  exit 1
fi
echo "The home's address: just its name on Tailscale (Enter for wuwa-home), or the name"
echo "Tailscale shows (wuwa-home.your-tailnet.ts.net), or its 100.x address."
read -r -p "Home address [wuwa-home]: " home
echo "The key: press Enter to take home.key from your Downloads folder (download it from"
echo "the home's data folder on the NAS first), or paste the key, or drag the file in."
read -r -p "Home key [Enter = home.key in Downloads]: " key
uv run python -m wuwa_vision home set "${home:-wuwa-home}" "$key"
read -r -p "Press Enter to close " _
