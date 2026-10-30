# The server (PLAN.md D129, D145): the dashboard and the data, on a box that is always on.
#
# No recogniser in here -- no torch, no model, no GPU. The machine with the game scans
# and sends finished scans; this shows them. The image is the app's base install and
# nothing else, built from the files beside this one (tools/make_nas_bundle.py lays
# them out).
#
# Tailscale is in here too, so a server is one container and shares nothing (D238): its own
# binaries from its own pinned image, unchanged -- the same version as deploy/tailscale-image,
# which is kept for compose files from before. It runs only when the compose file names this
# device (TS_HOSTNAME, entrypoint.sh). Off the PATH: web/tailnet.py looks for `tailscale` there
# to share a desktop's app, and a server is shared by the Serve settings below.
FROM tailscale/tailscale:v1.102.5 AS tailscale

FROM python:3.12-slim

# Where it comes from (D183): the published image is built from the public repository.
LABEL org.opencontainers.image.source="https://github.com/oguessyky/wuwa-inventory-vision" \
      org.opencontainers.image.description="WuWa Inventory Vision: the server (dashboard and data)" \
      org.opencontainers.image.licenses="Apache-2.0 AND BSD-3-Clause"

ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# OpenCV is in the base install (the dashboard reads crops with it); its wheel wants these.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

WORKDIR /app

# Dependencies first, exactly as locked: this layer is rebuilt only when they change.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# src/ holds the built pages too (src/wuwa_vision/web/ui): no Node here.
# tools/ is what 从 Wiki 更新 runs; assets/ the names that ship.
COPY src ./src
COPY tools ./tools
COPY assets ./assets
COPY LICENSE NOTICE CREDITS.md TERMS.md PRIVACY.md PRIVACY.zh-CN.md ./
RUN uv sync --frozen --no-dev
# which commit this was built from (written by make_nas_bundle): docker exec <name> cat /app/VERSION
COPY VERSION ./

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Serve: port 4000 of this device to the app on 127.0.0.1:4000, for the tailnet only -- never
# funnel, which would put it on the internet. Userspace networking: no /dev/net/tun, no NET_ADMIN.
# Logged in with the auth key once; after that the state in TS_STATE_DIR counts.
COPY --from=tailscale /usr/local/bin/containerboot /opt/tailscale/containerboot
COPY --from=tailscale /usr/local/bin/tailscale /opt/tailscale/tailscale
COPY --from=tailscale /usr/local/bin/tailscaled /opt/tailscale/tailscaled
COPY serve.json /config/serve.json
# Tailscale's licence, which BSD-3-Clause asks to travel with its binaries
COPY TAILSCALE-LICENSE /usr/share/licenses/tailscale/LICENSE
ENV TS_SERVE_CONFIG=/config/serve.json \
    TS_USERSPACE=true \
    TS_AUTH_ONCE=true \
    TS_STATE_DIR=/var/lib/tailscale

# The database, the scan crops, the catalogue and the upload key. Nothing else is kept.
VOLUME /app/data

# 127.0.0.1 and nothing else, as on a desktop (hard constraint 3). No port is published:
# Tailscale's Serve, beside it in this container, is the way in from the tailnet (D238).
HEALTHCHECK --interval=60s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:4000/api/sync/hello', timeout=4).status == 200 else 1)"

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-m", "wuwa_vision", "serve", "--server", "--local", "--port", "4000"]
