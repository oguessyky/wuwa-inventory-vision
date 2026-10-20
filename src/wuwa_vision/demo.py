# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Sample data for the first-time walk (D162).

The walk points at parts of pages -- a scan's ring, a round of buying, an item's
panel -- that a new user's empty database does not have yet. While it runs, the
pages ask for this instead: a database made here from the catalogue, the same
every time, kept in a temporary folder and never mixed with the user's own.

Nothing in it is anyone's: the counts are drawn from a fixed seed. It has a
complete scan of each bag tab, a wallet, a few base amounts below what is owned
(so there is something to buy), the echoes' base, and a handful of resonators
owned, with one plan.
"""

from __future__ import annotations

import random
import tempfile
import threading
from pathlib import Path

from . import planner
from .catalogue import Catalogue
from .store.db import ECHO_BASE, Observation, Store

#: The bag tabs a scan covers, in the game's order.
TABS = ("资源", "素材", "补给")
#: Counts to draw from, scaled up for the commoner things.
COUNTS = (0, 1, 2, 3, 5, 8, 12, 20, 35, 60, 120, 240)
#: Where the app keeps which rover is the user's (web.app ROVER_SETTING).
ROVER_GENDER = "rover.gender"
#: Bought in shops: each owned, and given a base above what is owned.
BASICS = ("面粉", "糖", "鸟蛋", "盐")
_lock = threading.Lock()
_made: dict[str, Path] = {}


def build(catalogue: Catalogue, path: Path) -> Path:
    """Write the sample database at `path` (a new file) and return it."""
    rng = random.Random(162)
    st = Store(path)
    try:
        for tab in TABS:
            names = sorted(n for n in catalogue.names()
                           if (catalogue.entry(n) or {}).get("tab") == tab)
            if not names:
                continue
            sid = st.begin_scan("demo", tab, len(names))
            rows = []
            for i, name in enumerate(names):
                rarity = int((catalogue.entry(name) or {}).get("rarity") or 1)
                count = rng.choice(COUNTS) * (6 - min(rarity, 5))
                if name in BASICS:   # owned, and below the base the sample gives them
                    count = 120
                rows.append(Observation(
                    frame="demo", row=i // 9, col=i % 9, icon_hash=f"demo{tab}{i}", rarity=rarity,
                    rarity_conf=1.0, count=count, count_conf=1.0, item_name=name,
                    item_key=f"demo:{name}", from_panel=True))
            st.add_observations(sid, rows)
            st.finish_scan(sid, frames=1, tiles=len(rows), complete=True)
        st.add_wallet(4_820_000, 1_640, 1.0)
        st.set_setting(ROVER_GENDER, "女")   # answered: the sample asks nothing
        # a few base amounts above what is owned: a round of buying to point at
        for name in BASICS:
            if catalogue.sold(name):
                st.set_base_amount(name, 400)
        st.set_base_amount(ECHO_BASE, 60)
        resonators = sorted((catalogue.builds.get("resonators") or {}).keys())[:8]
        for name in resonators:
            st.set_owned(name, True)
        if resonators:   # one plan, from nothing to a full build, as 规划 makes one
            st.add_plan("resonator", resonators[0], {
                "current": planner.full(catalogue, "resonator", resonators[0], top=False),
                "target": planner.full(catalogue, "resonator", resonators[0], top=True)})
    finally:
        st.close()
    return path


def database(catalogue: Catalogue) -> Path:
    """The sample database for this catalogue, made once per catalogue and process."""
    key = str(catalogue.directory.resolve())
    with _lock:
        path = _made.get(key)
        if path is None or not path.exists():
            folder = Path(tempfile.mkdtemp(prefix="wuwa-demo-"))
            path = build(catalogue, folder / "demo.sqlite")
            _made[key] = path
        return path
