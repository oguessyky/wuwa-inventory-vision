#!/bin/bash
# The first start of a server: if it has no database yet and one was put beside it to
# start from (seed-data/, copied once from the PC that has been scanning), take it in.
# After that the volume is the only copy that counts and seed-data/ can be deleted.
set -e

if [ ! -f /app/data/wuwa.sqlite ] && [ -f /seed/wuwa.sqlite ]; then
    echo "first start: taking in the data from seed-data/"
    cp -a /seed/. /app/data/
fi

if [ ! -f /app/data/server.key ] && [ ! -f /app/data/home.key ]; then   # home.key: before 1.2.0 (D225)
    echo "first start: the key a scanner needs will be the one line of server.key in the data folder"
fi

# Tailscale lives in this container when the compose file names this device (D238). A compose
# file from before names nothing here and has its own Tailscale container beside this one, and
# a server built from source has its own way in: then only the app runs, as it always has.
if [ -z "${TS_HOSTNAME:-}" ]; then
    exec "$@"
fi

# Whichever ends first ends the container, and Docker brings both back: half a server says
# nothing is wrong. Stopping the container stops both.
PATH="/opt/tailscale:$PATH" /opt/tailscale/containerboot &
env -u TS_AUTHKEY "$@" &
stop() { kill -TERM $(jobs -p) 2>/dev/null || true; }
trap stop TERM INT
set +e
wait -n
code=$?
stop
wait
exit "$code"
