# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Live scan state for the operator screen (PLAN.md D5, D25).

The scanner writes here after each view; the web page polls it. This is the
wucv overlay's information -- a box and a label on every tile -- shown on a local
page instead of drawn over the game, so nothing sits on top of the game window.

**PII (AGENTS.md constraint 4).** The picture published is cropped to the tile
grid: the union of the detected tile boxes, lightly padded. The live preview
reuses the crop of the last READ view -- the grid does not move on screen while
scrolling -- so no preview is published until a view has located the grid. The UID watermark
(bottom-right, below the detail panel) and co-op friend names (left rail) lie
outside it, so the published crop never contains them. The full frame is never
stored here.

Headless on purpose: this module draws nothing. The boxes are data; the page
draws them.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import cv2
import numpy as np

if TYPE_CHECKING:
    from .orchestrator import View

#: Padding around the grid crop, as a fraction of tile width.
GRID_PAD = 0.12
#: The published picture is scaled down to at most this width.
MAX_WIDTH = 1400
#: The live preview is re-encoded at most this often (seconds): ~8 fps is smooth
#: enough to follow a scroll. Measured at 3440x1440: 4 ms of the capture loop but
#: 23 ms of CPU per encode, ~18% of a core next to the game -- hence opt-in (D94).
PREVIEW_INTERVAL = 0.125
#: A page that said goodbye is believed gone after this long without asking again
#: (seconds, D156): a reload asks again well inside it.
PAGE_QUIET = 2.0


def grid_crop_box(
    shape: tuple[int, ...], boxes: list[tuple[int, int, int, int]]
) -> tuple[int, int, int, int]:
    """(x0, y0, x1, y1) covering every tile and nothing much else."""
    h, w = shape[:2]
    width = float(np.median([b[2] - b[0] for b in boxes]))
    pad = int(width * GRID_PAD)
    x0 = max(min(b[0] for b in boxes) - pad, 0)
    y0 = max(min(b[1] for b in boxes) - pad, 0)
    x1 = min(max(b[2] for b in boxes) + pad, w)
    y1 = min(max(b[3] for b in boxes) + pad, h)
    return x0, y0, x1, y1


def _encode(rgb: np.ndarray, box: tuple[int, int, int, int], scale: float, quality: int):
    x0, y0, x1, y1 = box
    crop = rgb[y0:y1, x0:x1]
    if scale < 1.0:
        crop = cv2.resize(
            crop, (int(crop.shape[1] * scale), int(crop.shape[0] * scale)),
            interpolation=cv2.INTER_AREA,
        )
    ok, jpeg = cv2.imencode(
        ".jpg", cv2.cvtColor(crop, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, quality]
    )
    return (jpeg.tobytes() if ok else None), (crop.shape[1], crop.shape[0])


def _match_dict(match: Any, row: Any) -> dict[str, Any]:
    """The scores behind a tile's label: what the page shows on each box."""
    out: dict[str, Any] = {"count_conf": round(float(row.count_conf), 2)}
    if match is not None:
        out.update(
            score=round(float(match.score), 3),
            margin=round(float(match.margin), 3),
            guess=match.item_name,
            sure=bool(getattr(match, "confident", False)),
        )
    return out


def _item_dict(item: Any) -> dict[str, Any]:
    return {
        "key": item.icon_hash,
        "rarity": item.rarity,
        "count": item.count,
        "name": item.item_name,
        "confirmed": bool(getattr(item, "confirmed", False)),
        "review": bool(item.needs_review),
        "click": bool(getattr(item, "needs_click", False)),
        "rivals": list(getattr(item, "rivals", ())),
    }


@dataclass
class LiveState:
    """Thread-safe snapshot of a running live scan."""

    picture: bool = False
    """Publish the game's grid as a picture under the boxes. Off by default (D94):
    the boxes carry everything the page says, and no game pixel leaves the scanner."""
    status: str = "starting"
    phase: str = "starting"
    """What the scanner is doing right now (orchestrator.run_live_scan, on_phase)."""
    phase_since: float = field(default_factory=time.time)
    version: int = 0
    frame_jpeg: bytes | None = None
    frame_size: tuple[int, int] = (0, 0)
    boxes: list[dict[str, Any]] = field(default_factory=list)
    tabs: list[dict[str, Any]] = field(default_factory=list)
    planned: list[str] = field(default_factory=list)
    """The tabs this scan covers, in the game's order (D190): each is on the page from the
    start, so the user sees which are not scanned yet."""
    current_tab: str | None = None
    items: list[dict[str, Any]] = field(default_factory=list)
    panel: dict[str, Any] | None = None
    sync: dict[str, Any] | None = None
    """How the talk with the home is going right now (`sync.Transfer.said`), or
    None when nothing is crossing (D156). Not part of `version`: it changes ten
    times a second, and a page is told it with every answer instead."""
    phone: dict[str, Any] = field(default_factory=dict)
    """Where the phone's page is, for the PC's page (D246): its `port`, with the `url` it
    was shared at or `why` it could not be. Told with every answer, like `sync`."""
    stopping: bool = False
    """A page pressed stop (D254), and the scan has yet to say it stopped."""
    _stopper: Callable[[], None] | None = field(default=None, repr=False)
    _asks: int = 0
    _bye: tuple[float, int] | None = None
    preview_jpeg: bytes | None = None
    preview_seq: int = 0
    _preview_at: float = 0.0
    _crop: tuple[int, int, int, int] | None = None
    _scale: float = 1.0
    _frame_shape: tuple[int, ...] | None = None
    _preview_ready: threading.Condition = field(
        default_factory=threading.Condition, repr=False
    )
    log: deque[tuple[float, str]] = field(default_factory=lambda: deque(maxlen=60))
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # ------------------------------------------------------------- writers

    def say(self, message: str) -> None:
        with self._lock:
            self.log.append((time.time(), message))
            self.version += 1

    def set_phase(self, phase: str) -> None:
        with self._lock:
            self.phase = phase
            self.phase_since = time.time()
            self.version += 1

    def set_status(self, status: str) -> None:
        with self._lock:
            self.status = status
            self.version += 1

    def update_view(self, view: View, tabs: list[Any]) -> None:
        """Publish one read view: the grid picture, a box per tile, the tab's items."""
        boxes = [t.box for t in view.tiles]
        crop_box = grid_crop_box(view.frame.rgb.shape, boxes)
        x0, y0, x1, y1 = crop_box
        scale = min(1.0, MAX_WIDTH / max(x1 - x0, 1))
        if self.picture:
            jpeg, size = _encode(view.frame.rgb, crop_box, scale, 82)
        else:  # boxes only: the page still needs the size they are laid out in
            jpeg, size = None, (int((x1 - x0) * scale), int((y1 - y0) * scale))
        matches = list(view.matches) + [None] * (len(view.tiles) - len(view.matches))

        stitcher = view.tab.stitcher
        new_keys = {i.icon_hash for i in stitcher.last_new}
        tile_boxes = []
        for tile, row, match in zip(view.tiles, view.rows, matches, strict=True):
            item = stitcher.items.get(row.item_key or "")
            bx0, by0, bx1, by1 = tile.box
            tile_boxes.append(
                {
                    "x": round((bx0 - x0) * scale), "y": round((by0 - y0) * scale),
                    "w": round((bx1 - bx0) * scale), "h": round((by1 - by0) * scale),
                    **(_item_dict(item) if item is not None else {}),
                    "new": row.item_key in new_keys,
                    "selected": row.from_panel,
                    **_match_dict(match, row),
                }
            )

        panel = view.tab.report.last_panel
        with self._lock:
            if jpeg is not None:
                self.frame_jpeg = jpeg
            if jpeg is not None or not self.picture:
                self.frame_size = size
            self._crop, self._scale = crop_box, scale
            self._frame_shape = view.frame.rgb.shape
            self.boxes = tile_boxes
            self.current_tab = view.tab.label
            self.items = [_item_dict(i) for i in stitcher.sorted_items()]
            self.tabs = [_tab_dict(t) for t in tabs]
            if panel is not None:
                self.panel = {"name": panel.name, "category": panel.category,
                              "owned": panel.owned, "level": panel.level,
                              "rank": panel.rank, "tab": view.tab.label}
            self.status = "capturing"
            self.version += 1

    def offer_preview(self, rgb: np.ndarray) -> None:
        """Publish a live frame, cropped like the last read view. Throttled."""
        if not self.picture:
            return
        now = time.monotonic()
        if now - self._preview_at < PREVIEW_INTERVAL:
            return
        with self._lock:
            crop, scale, shape = self._crop, self._scale, self._frame_shape
        if crop is None or rgb.shape != shape:
            return  # grid not located yet, or the window changed size
        self._preview_at = now
        jpeg, _ = _encode(rgb, crop, scale, 70)
        if jpeg is None:
            return
        with self._preview_ready:
            self.preview_jpeg = jpeg
            self.preview_seq += 1
            self._preview_ready.notify_all()

    def next_preview(self, after: int, timeout: float = 1.0) -> tuple[int, bytes | None]:
        """Block until a preview newer than `after` exists (or timeout)."""
        with self._preview_ready:
            self._preview_ready.wait_for(lambda: self.preview_seq > after, timeout)
            return self.preview_seq, self.preview_jpeg

    def rename(self, wrong: str, right: str) -> None:
        """Show a name correction at once; the scanner applies it on its next view."""
        with self._lock:
            for entry in (*self.items, *self.boxes):
                if entry.get("name") == wrong:
                    entry["name"] = right
            if self.panel and self.panel.get("name") == wrong:
                self.panel["name"] = right
            self.version += 1

    def plan_tabs(self, labels: list[str]) -> None:
        """The tabs this scan covers (D190): shown from the start, those not scanned marked."""
        with self._lock:
            self.planned = list(labels)
            self.version += 1

    def _tabs(self) -> list[dict[str, Any]]:
        """Every tab to scan in the plan's order -- read or not yet -- then any other read."""
        seen = {t["label"]: t for t in self.tabs}
        out = [seen.get(label) or {"label": label, "found": 0, "total": None, "complete": False,
                                   "overcount": False, "gaps": 0, "named": 0, "panel_reads": 0,
                                   "review": 0, "click": 0, "visited": False}
               for label in self.planned]
        return out + [t for t in self.tabs if t["label"] not in self.planned]

    def update_tabs(self, tabs: list[Any]) -> None:
        with self._lock:
            self.tabs = [_tab_dict(t) for t in tabs]
            self.version += 1

    def set_sync(self, said: dict[str, Any] | None) -> None:
        with self._lock:
            self.sync = said

    def set_phone(self, said: dict[str, Any]) -> None:
        with self._lock:
            self.phone = said

    def set_stopper(self, stop: Callable[[], None]) -> None:
        """What a page's stop button does: press the panic key (D254)."""
        with self._lock:
            self._stopper = stop
            self.version += 1

    def ask_stop(self) -> bool:
        """A page pressed stop. False with no scan to stop; pressed twice, it stops once."""
        with self._lock:
            stop = None if self.status == "stopped" else self._stopper
            if stop is None:
                return False
            first = not self.stopping
            self.stopping = True
            self.version += 1
        if first:
            stop()
        return True

    # ------------------------------------------------- is the PC's page open (D156)

    def asked(self) -> None:
        """The PC's live page asked for the state: it is open."""
        with self._lock:
            self._asks += 1

    def bye(self) -> None:
        """A page said it is going. A hint, not a fact: `page_gone` decides."""
        with self._lock:
            # when, and how often the page had asked by then: "has it asked since"
            # is then a count, which a coarse clock cannot get wrong
            self._bye = (time.monotonic(), self._asks)

    def page_gone(self, quiet: float = PAGE_QUIET) -> bool:
        """Was the PC's page closed? It said goodbye and has not asked since.

        A reload says goodbye too, and so can any other page in the browser (the
        goodbye is a plain POST to 127.0.0.1): either way the page that is still
        open asks again within `quiet`, and it is not gone. A page that was never
        opened never said goodbye."""
        with self._lock:
            bye, asks = self._bye, self._asks
        return bye is not None and asks == bye[1] and time.monotonic() - bye[0] >= quiet

    # -------------------------------------------------------------- reader

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "status": self.status,
                "phase": self.phase,
                "phase_since": self.phase_since,
                "version": self.version,
                "picture": self.picture,
                "has_view": self._crop is not None,
                "has_frame": self.frame_jpeg is not None,
                "has_preview": self.preview_jpeg is not None,
                "frame_size": list(self.frame_size),
                "boxes": list(self.boxes),
                "tabs": self._tabs(),
                "current_tab": self.current_tab,
                "items": list(self.items),
                "panel": self.panel,
                "sync": self.sync,
                "phone": dict(self.phone),
                "can_stop": self._stopper is not None and self.status != "stopped",
                "stopping": self.stopping,
                "log": [{"t": t, "msg": m} for t, m in self.log],
            }

    def jpeg(self) -> bytes | None:
        with self._lock:
            return self.frame_jpeg


def needs_you(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """What the scan is waiting on the user for, most pressing first (D153).

    With one screen the game covers the terminal, and these are the lines that
    would have been read there. Each is a kind and its facts; the page words it.
    """
    if snapshot.get("status") == "stopped":
        return []  # the scan is over: there is nothing left to do for it
    here = snapshot.get("current_tab")
    tab = next((t for t in snapshot.get("tabs", []) if t["label"] == here), None)
    needs: list[dict[str, Any]] = []
    if tab and tab["gaps"] and not tab["complete"]:
        # Not on a complete tab: the game's own count says nothing is missing.
        needs.append({"kind": "gap", "tab": here, "views": tab["gaps"]})
    needs += [{"kind": "click", "key": item["key"], "rivals": item["rivals"]}
              for item in snapshot.get("items", []) if item["click"]]
    needs += [{"kind": "click-there", "tab": t["label"], "items": t["click"]}
              for t in snapshot.get("tabs", []) if t["click"] and t["label"] != here]
    if tab and tab["complete"]:
        needs.append({"kind": "done", "tab": here, "total": tab["total"]})
    return needs


def _tab_dict(tab: Any) -> dict[str, Any]:
    s = tab.stitcher
    return {
        "label": tab.label,
        "found": s.unique,
        "total": tab.report.header_total,
        "complete": s.complete,
        "overcount": s.overcount,
        "gaps": s.gaps,
        "named": s.named,
        "panel_reads": tab.report.panel_reads,
        "review": s.needs_review,
        "click": sum(1 for i in s.items.values() if i.needs_click),
        "visited": True,
    }
