# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Replay fixture frames into the live page, with the game not running.

Serves http://127.0.0.1:8711/live and feeds it one fixture view every few
seconds, in a loop -- enough to see and work on the page without a live scan.
The phone's page (D153) is served beside it on 8713; `--share` hands that one to
your tailnet, as `wuwa live --share` would, to try it on the phone itself.

Run:  uv run python tools/demo_live_page.py [--port 8711] [--share]
"""

from __future__ import annotations

import argparse
import tempfile
import threading
import time
from pathlib import Path

import numpy as np
import uvicorn
from PIL import Image

from wuwa_vision.capture.base import Frame
from wuwa_vision.scan.live_state import LiveState
from wuwa_vision.scan.orchestrator import run_live_scan
from wuwa_vision.store.db import Store
from wuwa_vision.web import tailnet
from wuwa_vision.web.app import PHONE_PORT, create_app, create_phone_app

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
PAGES = ["mat_top_selected", "mat_scrolled_a", "mat_scrolled_b", "res_21_9_a", "res_21_9_c"]


def frames(seconds_per_page: float):
    seq = 0
    while True:
        for name in PAGES:
            with Image.open(FIXTURES / f"{name}.webp") as im:
                rgb = np.asarray(im.convert("RGB"))
            until = time.monotonic() + seconds_per_page
            while time.monotonic() < until:
                yield Frame(rgb=rgb, source=f"demo:{name}", seq=seq)
                seq += 1
                time.sleep(0.05)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8711)
    parser.add_argument("--phone-port", type=int, default=PHONE_PORT)
    parser.add_argument("--share", action="store_true",
                        help="share the phone's page with your tailnet while this runs")
    parser.add_argument("--seconds", type=float, default=4.0, help="per fixture page")
    args = parser.parse_args()

    db = Path(tempfile.mkdtemp(prefix="wuwa-demo-")) / "demo.sqlite"
    store = Store(db)
    state = LiveState()
    for app, port in ((create_app(db, live=state), args.port),
                      (create_phone_app(db, state), args.phone_port)):
        server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
        threading.Thread(target=server.run, daemon=True).start()
    print(f"demo live page : http://127.0.0.1:{args.port}/live")
    print(f"demo phone page: http://127.0.0.1:{args.phone_port}")
    if args.share:
        shared, why = tailnet.open_share(args.phone_port)
        print(f"  on your phone: {shared.url}" if shared else f"  not shared ({why})")

    state.set_status("capturing")
    state.say("demo: replaying fixture frames")

    def on_view(view) -> None:  # noqa: ANN001
        state.update_view(view, view.tabs)
        s = view.tab.stitcher
        state.say(f"[{view.tab.label}] view {view.tab.report.frames_used}: "
                  f"+{len(s.last_new)} new -> {s.progress()}")
        if view.tab.report.last_panel is not None:
            p = view.tab.report.last_panel
            state.say(f"= selected: {p.name}  拥有 {p.owned}")

    run_live_scan(
        frames(args.seconds), store, source="demo", stop_when_complete=False,
        max_seconds=10**9, on_view=on_view,
        on_tab=lambda tab: state.say(f"-> tab {tab.label}"),
        on_phase=state.set_phase,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
