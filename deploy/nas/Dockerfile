# The home (PLAN.md D129, D145): the dashboard and the data, on a box that is always on.
#
# No recogniser in here -- no torch, no model, no GPU. The machine with the game scans
# and sends finished scans; this shows them. The image is the app's base install and
# nothing else, built from the files beside this one (tools/make_nas_bundle.py lays
# them out).
FROM python:3.12-slim

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

# The database, the scan crops, the catalogue and the upload key. Nothing else is kept.
VOLUME /app/data

# 127.0.0.1 and nothing else, as on a desktop (hard constraint 3). No port is published:
# the container shares a network with Tailscale, which serves it to the tailnet (docker-compose.yaml).
HEALTHCHECK --interval=60s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:4000/api/sync/hello', timeout=4).status == 200 else 1)"

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-m", "wuwa_vision", "serve", "--home", "--local", "--port", "4000"]
