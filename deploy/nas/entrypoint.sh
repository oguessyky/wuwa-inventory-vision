#!/bin/sh
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

exec "$@"
