# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Which tile is selected -- the one the detail panel is describing.

Clicking a tile draws a pale-gold outline around it, and the right-hand panel
then shows that item's name and `拥有 N`. Knowing the selected tile is what lets a
panel read be attached to one grid item (PLAN.md D24). The user does the
clicking; this only looks.

The selected tile's contour is its outline, 6-10% larger than a tile; tile
extraction shrinks it back to tile size (D32), so the gold line sits just outside
the box. A band straddling the box edge is scored, on the top, left and right
only -- the bottom band is the rarity bar, and a 5-star bar is gold too.

Measured over the fixtures and train captures: selected tiles score 0.199-0.224,
unselected tiles (5-star gold backgrounds included) at most 0.056.
"""

from __future__ import annotations

import numpy as np

from .tiles import Tile

#: Fraction of edge-band pixels that must be outline gold.
MIN_SCORE = 0.15
#: The winner must also clearly beat the runner-up.
MIN_RATIO = 2.0
#: Band depth as a fraction of tile width (12 px on a ~225 px tile).
BAND = 0.053


def outline_score(rgb: np.ndarray, box: tuple[int, int, int, int]) -> float:
    # Tile boxes are tile-sized even when selected (the outline contour is shrunk
    # back, D32), so the outline sits just OUTSIDE the box: score a band that
    # straddles the edge, `k` px either side.
    k = max(2, int(round((box[2] - box[0]) * BAND)))
    h, w = rgb.shape[:2]
    x0, y0 = max(box[0] - k, 0), max(box[1] - k, 0)
    x1, y1 = min(box[2] + k, w), min(box[3] + k, h)
    tile = rgb[y0:y1, x0:x1]
    if tile.size == 0:
        return 0.0
    k *= 2
    mask = np.zeros(tile.shape[:2], dtype=bool)
    mask[:k, :] = True
    mask[:, :k] = True
    mask[:, -k:] = True
    mask[-k:, :] = False
    px = tile[mask].astype(np.int16)
    r, g, b = px[:, 0], px[:, 1], px[:, 2]
    gold = (r > 190) & (g > 175) & (r - b > 45) & (b > 90)
    return float(gold.mean())


def selected_index(rgb: np.ndarray, tiles: list[Tile]) -> int | None:
    """Index of the selected tile in `tiles`, or None when none is visible."""
    if not tiles:
        return None
    scores = [outline_score(rgb, t.box) for t in tiles]
    order = np.argsort(scores)[::-1]
    best = scores[int(order[0])]
    runner = scores[int(order[1])] if len(order) > 1 else 0.0
    if best < MIN_SCORE or best < MIN_RATIO * runner:
        return None
    return int(order[0])
