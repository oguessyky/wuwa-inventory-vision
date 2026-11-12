# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Where a resonator's screens, as read (D270), go.

The 属性详情 screen names the resonator; 技能 and 武器 do not, so they are the last 属性详情's
resonator's -- the game opens them from that resonator's page. An echo's panel names who holds
it. Every reading is kept per resonator (`Store.character_reads`), and the level and skill levels
also fill that resonator's progress (D57): the scan is a way in besides typing. The stat nodes
and a chain set by hand are left alone.
"""

from __future__ import annotations

import numpy as np

from ..calc import ascension_for_cap
from ..ocr import character
from ..store.db import Store

#: Progress is kept by the app's names; a 漂泊者 form's is not told apart here, so it is left.
_ROVER = "漂泊者"


class CharacterReader:
    def __init__(self, store: Store) -> None:
        self.store = store
        self.current: str | None = None

    def take(self, reading: dict) -> str | None:
        """Keep one screen's reading; the resonator it was kept under, or None."""
        kind = reading.get("kind")
        if kind == "attributes":
            self.current = reading.get("name")
            if not self.current:
                return None
            self.store.save_character_read(self.current, "attributes", reading)
            self._progress(level=reading.get("level"), cap=reading.get("cap"))
            return self.current
        if kind in ("skills", "weapon"):
            if not self.current:
                return None
            self.store.save_character_read(self.current, kind, reading)
            if kind == "skills":
                self._progress(skills=reading.get("skills") or {})
            return self.current
        if kind == "echo":
            holder = reading.get("holder")
            if not holder or not reading.get("name"):
                return None
            self.store.save_character_read(holder, "echo", reading, key=reading["name"])
            return holder
        return None

    def _progress(
        self, *, level: int | None = None, cap: int | None = None, skills: dict | None = None
    ) -> None:
        name = self.current
        if not name or name.startswith(_ROVER):
            return
        mine = self.store.progress().get(name) or {}
        state = dict(mine.get("state") or {})
        if level:
            state["level"] = int(level)
            state["ascension"] = ascension_for_cap(int(cap or level))
        if skills:
            state["skills"] = {**(state.get("skills") or {}), **skills}
        if state == (mine.get("state") or {}):
            return
        state.setdefault("nodes", {})
        state.setdefault("skills", {})
        self.store.set_progress(name, True, state)


def _lists() -> dict:
    """The names a reading snaps onto: 计算's data (D268) when it is fetched, else the
    catalogue's resonators and weapons."""
    from ..calc_data import cached
    from ..catalogue import CATALOGUE_DIR, Catalogue

    data = cached(CATALOGUE_DIR)
    if data:
        return {
            "names": {n: r.get("element") for n, r in data["roles"].items()},
            "echoes": list(data.get("echoes") or {}),
            "sets": list(data.get("sets") or {}),
            "weapons": list(data.get("weapons") or {}),
        }
    catalogue = Catalogue.load()
    return {
        "names": {n: None for n in catalogue.builds.get("resonators") or {}},
        "echoes": [],
        "sets": [],
        "weapons": list(catalogue.builds.get("weapons") or {}),
    }


#: The echo panel, as the window's height from its right edge (ocr/character.py), and how
#: different its small picture must be to be another echo.
_PANEL = (0.64, 0.1, 0.0, 0.7)
_CHANGED = 6.0


def _thumb(rgb: np.ndarray) -> np.ndarray:
    h, w = rgb.shape[:2]
    left, top, right, bottom = _PANEL
    crop = rgb[int(top * h) : int(bottom * h), w - int(left * h) : w - int(right * h)]
    step = max(1, crop.shape[0] // 48)
    return crop[::step, ::step].astype(np.float32).mean(axis=2)


class CharacterScreens:
    """A live scan's eye for a resonator's own screens (D270): `look` reads a still frame that is
    one of them and keeps what it says; `panel_changed` tells a click on another echo in the bag,
    which changes too little of the window for the frame gate."""

    def __init__(self, store: Store, lists: dict | None = None) -> None:
        self.reader = CharacterReader(store)
        self.lists = lists if lists is not None else _lists()
        self.last_kind: str | None = None
        self._panel: np.ndarray | None = None

    def look(self, rgb: np.ndarray) -> dict | None:
        said = character.read(rgb, **self.lists)
        if said is None:
            self.last_kind = None
            return None
        self.last_kind = said["kind"]
        if said["kind"] == "echo":
            self._panel = _thumb(rgb)
        return {"kind": said["kind"], "resonator": self.reader.take(said)}

    def panel_changed(self, rgb: np.ndarray) -> bool:
        if self.last_kind != "echo" or self._panel is None:
            return False
        now = _thumb(rgb)
        if now.shape != self._panel.shape:
            return True
        return float(np.abs(now - self._panel).mean()) > _CHANGED
