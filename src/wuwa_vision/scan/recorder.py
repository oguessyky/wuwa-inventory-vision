# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Run record: everything one live session read, kept on disk for diagnosis.

Each read view leaves, under `data/runs/<start time>/`:

    views/NNN.jpg          the grid, cropped exactly like the live page
    views/NNN.json         every tile's reads and scores, the panel, timings
    counts/NNN_TT.png      each tile's count crop, as OCR saw it
    panels/NNN.png         the detail-panel crop, when one was read
    events.jsonl           the console messages and gate diagnostics, timestamped

Icon crops are not duplicated: the JSON names them by hash, and they are already
in `data/icons/`. Only the last `KEEP` runs are kept -- this is a scratch record
for "what went wrong in that run", not an archive.

**PII (AGENTS.md constraint 4).** Nothing here holds the UID or friend names:
the grid crop is `live_state.grid_crop_box` (tested to exclude the UID corner and
the left rail), count crops are inside tiles, and the panel crop is the upper
half of the window right of the grid, while the UID sits bottom-right.
"""

from __future__ import annotations

import json
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import cv2
import numpy as np

from .live_state import grid_crop_box

if TYPE_CHECKING:
    from .orchestrator import View

#: Runs kept on disk, newest first; older ones are deleted when a run starts.
KEEP = 5


def _png(path: Path, rgb: np.ndarray) -> None:
    if rgb.size:
        cv2.imwrite(str(path), cv2.cvtColor(np.ascontiguousarray(rgb), cv2.COLOR_RGB2BGR))


class RunRecorder:
    """Writes one live session's reads to a timestamped folder."""

    def __init__(self, root: Path, keep: int = KEEP) -> None:
        root.mkdir(parents=True, exist_ok=True)
        old = sorted((p for p in root.iterdir() if p.is_dir()), reverse=True)
        for stale in old[max(keep - 1, 0):]:
            shutil.rmtree(stale, ignore_errors=True)
        self.dir = root / datetime.now().strftime("%Y%m%d-%H%M%S")
        for sub in ("views", "counts", "panels"):
            (self.dir / sub).mkdir(parents=True, exist_ok=True)
        self.views = 0
        self._events = (self.dir / "events.jsonl").open("a", encoding="utf-8")

    def event(self, kind: str, **data: Any) -> None:
        if self._events.closed:
            return
        line = {"t": round(time.time(), 3), "kind": kind, **data}
        self._events.write(json.dumps(line, ensure_ascii=False) + "\n")
        self._events.flush()

    def view(self, view: View) -> None:
        self.views += 1
        n = f"{self.views:03d}"
        rgb = view.frame.rgb
        boxes = [t.box for t in view.tiles]
        x0, y0, x1, y1 = grid_crop_box(rgb.shape, boxes)
        cv2.imwrite(
            str(self.dir / "views" / f"{n}.jpg"),
            cv2.cvtColor(np.ascontiguousarray(rgb[y0:y1, x0:x1]), cv2.COLOR_RGB2BGR),
            [cv2.IMWRITE_JPEG_QUALITY, 90],
        )

        stitcher, report = view.tab.stitcher, view.tab.report
        new = {i.icon_hash for i in stitcher.last_new}
        matches = list(view.matches) + [None] * (len(view.tiles) - len(view.matches))
        tiles = []
        for i, (tile, row, match) in enumerate(zip(view.tiles, view.rows, matches, strict=True)):
            _png(self.dir / "counts" / f"{n}_{i:02d}.png", tile.count_crop)
            item = stitcher.items.get(row.item_key or "")
            tiles.append({
                "i": i, "row": tile.row, "col": tile.col,
                # Box in grid-crop coordinates, so it lines up with views/NNN.jpg.
                "box": [tile.box[0] - x0, tile.box[1] - y0, tile.box[2] - x0, tile.box[3] - y0],
                "icon": row.icon_hash, "item": row.item_key, "new": row.item_key in new,
                "rarity": row.rarity, "rarity_conf": round(row.rarity_conf, 3),
                "count": row.count, "count_conf": round(row.count_conf, 3),
                "name": row.item_name, "from_panel": row.from_panel,
                "match": None if match is None else {
                    "guess": match.item_name, "score": round(float(match.score), 4),
                    "margin": round(float(match.margin), 4),
                    "sure": bool(getattr(match, "confident", False)),
                    "rivals": list(getattr(match, "rivals", ())),
                },
                "item_name": item.item_name if item else None,
                "item_count": item.count if item else None,
                "confirmed": bool(item.confirmed) if item else False,
            })

        panel = None
        attempt = report.panel_attempt
        if view.panel is not None or attempt:
            from ..ocr.panel import crop_panel

            # Failed reads too: their crop and raw lines are what explain them.
            _png(self.dir / "panels" / f"{n}.png", crop_panel(rgb, boxes))
            p = view.panel
            panel = {
                "name": p.name if p else None, "category": p.category if p else None,
                "owned": p.owned if p else None,
                "confidence": round(p.confidence, 3) if p else None,
                "attached": report.last_panel is not None,
                "ocr": [[round(y), t, round(c, 3)] for y, t, c in (attempt or [])],
            }

        record = {
            "view": self.views, "frame": f"{view.frame.source.strip()}#{view.frame.seq}",
            "t": round(time.time(), 3), "tab": report.tab_label,
            "header_total": report.header_total, "found": stitcher.unique,
            "registered": stitcher.last_registered, "gaps": stitcher.gaps,
            # enough to tell a mis-stitch from a miss when replaying a run (D96)
            "misplaced": stitcher.misplaced,
            "novelty": view.novelty, "timings": view.timings,
            "panel": panel, "tiles": tiles,
        }
        (self.dir / "views" / f"{n}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        self.event("view", view=self.views, found=stitcher.unique, timings=view.timings,
                   panel=panel)

    def close(self) -> None:
        self._events.close()
