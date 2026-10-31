#!/bin/bash
# The first start of a server: if it has no database yet and one was put beside it to
# start from (seed-data/, copied once from the PC that has been scanning), take it in.
# After that the volume is the only copy that counts and seed-data/ can be deleted.
set -e

if [ ! -f /app/data/wuwa.sqlite ] && [ -f /seed/wuwa.sqlite ]; then
    echo "first start: taking in the data from seed-data/"
    cp -a /seed/. /app/data/
fi

if [ ! -f /app/data/server.key ]; then
    echo "first start: the key a scanner needs will be the one line of server.key in the data folder"
fi

# Tailscale lives in this container when the compose file names this device (D238). A compose
# file from before names nothing here and has its own Tailscale container beside this one, and
# a server built from source has its own way in: then only the app runs, as it always has.
if [ -z "${TS_HOSTNAME:-}" ]; then
    exec "$@"
fi

# Tailscale is started again on its own when it ends: its start gives up after a minute with no
# working login, and that must not take the app down with it. The app ending ends the container,
# and Docker brings both back. Stopping the container stops both.
set +e
keep_tailscale() {
    trap 'kill -TERM "$boot" 2>/dev/null; wait "$boot"; exit 0' TERM INT
    while true; do
        PATH="/opt/tailscale:$PATH" /opt/tailscale/containerboot &
        boot=$!
        wait "$boot"
        echo "tailscale ended: starting it again in 10 seconds"
        sleep 10 &
        wait $!
    done
}

keep_tailscale &
tailscale=$!
env -u TS_AUTHKEY "$@" &
app=$!
stop() { kill -TERM "$app" "$tailscale" 2>/dev/null || true; }
trap stop TERM INT
wait "$app"
code=$?
stop
wait
exit "$code"
