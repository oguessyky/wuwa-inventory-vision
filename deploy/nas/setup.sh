#!/bin/sh
# Set the home up on a NAS, and bring it up to date afterwards (docs/nas.md).
#
#   sh setup.sh
#
# Run it in the folder this file is in, on the NAS. It does four things and says each:
#   1. works out which network the app must share to be on the same 127.0.0.1 as Tailscale
#   2. builds the image and starts the container            (docker compose up -d --build)
#   3. tells Tailscale to serve it to your tailnet, once    (tailscale serve --bg; never funnel)
#   4. prints the address to open and the key a scanner needs
#
# Safe to run again: it rebuilds, restarts, and leaves .env and the data alone.
set -e
cd "$(dirname "$0")"

# Tailscale's container. Empty ("") if Tailscale is installed on the NAS itself.
TS=${TAILSCALE_CONTAINER-tailscale}
ts() { if [ -n "$TS" ]; then docker exec "$TS" tailscale "$@"; else tailscale "$@"; fi; }

[ -f .env ] || { cp .env.example .env; echo "made .env from .env.example"; }

if ! grep -q '^WUWA_NETWORK=' .env; then
    mode=host
    if [ -n "$TS" ]; then
        mode=$(docker inspect -f '{{.HostConfig.NetworkMode}}' "$TS")
        [ "$mode" = host ] || mode="container:$TS"
    fi
    echo "WUWA_NETWORK=$mode" >> .env
    echo "1. network: Tailscale ($TS) is on '$mode' -- written to .env"
else
    echo "1. network: $(grep '^WUWA_NETWORK=' .env) (from .env)"
fi

data=$(grep '^WUWA_DATA=' .env | cut -d= -f2-)
case "$data" in /*) mkdir -p "$data" ;; esac

echo "2. building and starting (the first build takes a few minutes)"
docker compose up -d --build

name=$(grep '^WUWA_CONTAINER=' .env | cut -d= -f2-)
name=${name:-wuwa-vision}
printf "   waiting for it to answer"
for _ in $(seq 1 60); do
    if docker exec "$name" python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:4000/api/sync/hello', timeout=3)" 2>/dev/null; then
        up=1; break
    fi
    printf "."; sleep 2
done
echo
[ -n "$up" ] || { echo "it did not start: docker compose logs --tail 40 wuwa"; exit 1; }

echo "3. serving it to your tailnet (your own devices only)"
ts serve --bg --http=4000 http://127.0.0.1:4000 >/dev/null
host=$(ts status --self --json 2>/dev/null | sed -n 's/.*"DNSName": *"\([^"]*\)\.".*/\1/p' | head -1)

echo
echo "4. open:  http://${host:-<this NAS's tailnet name>}:4000"
echo "   on the PC with the game, once:"
echo "     uv run python -m wuwa_vision home set http://${host:-<name>}:4000 $(docker exec "$name" cat /app/data/home.key)"
