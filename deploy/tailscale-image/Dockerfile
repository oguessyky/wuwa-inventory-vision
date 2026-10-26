# The home's Tailscale, under this app's name (PLAN.md D191): Tailscale's own official image,
# unchanged -- no package added, nothing rebuilt -- with the home's Serve settings and defaults
# built in, so a NAS's image list says whose it is and the compose file says only the key and
# the name. Published by the public repository's workflow beside the app's image.
#
# Serve: port 4000 of this device to the app on 127.0.0.1:4000, for the tailnet only --
# never funnel, which would put it on the internet. Userspace networking: no /dev/net/tun,
# no NET_ADMIN. Logged in with the auth key once; after that the state in TS_STATE_DIR counts.
FROM tailscale/tailscale:v1.102.5

LABEL org.opencontainers.image.source="https://github.com/oguessyky/wuwa-inventory-vision" \
      org.opencontainers.image.description="WuWa Inventory Vision: the home's Tailscale (tailscale/tailscale, unchanged, with the home's Serve settings)" \
      org.opencontainers.image.licenses="BSD-3-Clause"

COPY serve.json /config/serve.json
# Tailscale's licence, which BSD-3-Clause asks to travel with its binaries; its own image has
# no copy inside
COPY TAILSCALE-LICENSE /usr/share/licenses/tailscale/LICENSE

ENV TS_SERVE_CONFIG=/config/serve.json \
    TS_USERSPACE=true \
    TS_AUTH_ONCE=true \
    TS_STATE_DIR=/var/lib/tailscale \
    TS_HOSTNAME=wuwa-home
