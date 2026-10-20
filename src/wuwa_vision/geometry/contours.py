# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Contour-based tile detection.

Ported from the sibling `wucv` project (`reference_item_grid_detection.py`).

Where `lattice.py` fits one global periodic grid and derives every tile box from
pitch + extent, this finds each tile's own bounding box from its contour. That is
the important difference: per-tile boxes track each tile's true rectangle instead
of inheriting a single fitted extent, which is what made crop sizes vary between
frames (203x211 / 204x212 / 204x167 for the same UI).

Pipeline: Canny -> dilate -> external contours -> area and aspect filter ->
median width/height filter -> drop frame-edge boxes.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

__all__ = ["TileBox", "ContourGrid", "detect_boxes", "detect_grid"]

CANNY_LO, CANNY_HI = 40, 120
MIN_AREA = 3000
ASPECT_LO, ASPECT_HI = 0.6, 1.1
#: Boxes whose size deviates more than this from the median are not tiles.
SIZE_TOLERANCE = 0.25
#: Boxes touching the frame edge are clipped tiles; their crops would be partial.
EDGE_MARGIN = 5
#: A box this much shorter than the median is a row clipped by the SCROLL VIEW, not
#: the frame edge: the view masks tiles mid-grid, so EDGE_MARGIN never sees them.
#: Its bar and count are cut off, so it reads as 1-star with no count, and those
#: ghosts broke the next frame's registration: it placed the same row one pitch
#: lower as six new items. Live ghost: 0.75. Measured on fixtures and captures:
#: clipped rows 0.77-0.89, real tiles never below 0.93 (1-star flower rows).
MAX_SHORTFALL = 0.09
#: A tile is at least this tall relative to the WINDOW (a ratio, not a pixel size,
#: so it holds at any resolution). Needed because the size filter below is relative
#: to the median box: on a frame with no grid (mid tab switch, grid still drawing)
#: the left-rail tab icons are the majority, set the median, and were read as items.
#: Measured: real tiles 0.140-0.20 of window height on every full-window fixture and
#: capture (0.146 live at 2560x1600); rail icons at most ~0.09 (D27).
MIN_TILE_HEIGHT_FRAC = 0.11
#: A real grid spans several columns. The rail is one column of icons.
MIN_COLUMNS = 2


@dataclass(frozen=True, slots=True)
class TileBox:
    x: int
    y: int
    w: int
    h: int

    @property
    def box(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.x + self.w, self.y + self.h)


@dataclass(frozen=True, slots=True)
class ContourGrid:
    """Detected tiles, organised into rows and columns."""

    boxes: tuple[TileBox, ...]
    rows: tuple[int, ...]
    """Row origin y for each detected row."""
    cols: tuple[int, ...]
    """Column origin x for each detected column."""

    @property
    def shape(self) -> tuple[int, int]:
        return (len(self.rows), len(self.cols))


def detect_boxes(rgb: np.ndarray) -> list[TileBox]:
    """Find per-tile bounding boxes. Returns [] when the frame has no grid."""
    grey = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(grey, CANNY_LO, CANNY_HI)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    edges = cv2.dilate(edges, kernel, iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates: list[TileBox] = []
    min_h = rgb.shape[0] * MIN_TILE_HEIGHT_FRAC
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if w * h < MIN_AREA or h < min_h:
            continue
        if not (ASPECT_LO <= w / h <= ASPECT_HI):
            continue
        candidates.append(TileBox(x, y, w, h))

    if not candidates:
        return []

    median_w = float(np.median([b.w for b in candidates]))
    median_h = float(np.median([b.h for b in candidates]))
    height = rgb.shape[0]

    keep: list[TileBox] = []
    for b in candidates:
        if abs(b.w - median_w) > median_w * SIZE_TOLERANCE:
            continue
        if abs(b.h - median_h) > median_h * SIZE_TOLERANCE:
            continue
        if b.h < median_h * (1.0 - MAX_SHORTFALL):
            continue
        if b.y <= EDGE_MARGIN or b.y + b.h >= height - EDGE_MARGIN:
            continue
        keep.append(b)
    return keep


def _cluster(values: list[int], gap: int) -> list[int]:
    """Group near-equal coordinates, returning each group's median."""
    if not values:
        return []
    out: list[int] = []
    run = [values[0]]
    for v in values[1:]:
        if v - run[-1] <= gap:
            run.append(v)
        else:
            out.append(int(np.median(run)))
            run = [v]
    out.append(int(np.median(run)))
    return out


#: A real grid column holds tiles from most rows. A lone box in the detail panel
#: does not, and passes the area/aspect filters on its own.
MIN_COLUMN_OCCUPANCY = 0.5


def detect_grid(rgb: np.ndarray) -> ContourGrid:
    """Detect tiles and infer the row/column structure they form.

    Sparse columns are dropped. The detail panel contains rounded-rect elements
    that survive the per-box filters -- on res_21_9_rgba one produced a spurious
    10th column at x=3056 with a visibly different aspect ratio. A real column is
    populated across rows; a panel artefact is not.
    """
    boxes = detect_boxes(rgb)
    if not boxes:
        return ContourGrid((), (), ())

    median_w = float(np.median([b.w for b in boxes]))
    median_h = float(np.median([b.h for b in boxes]))
    cols = _cluster(sorted(b.x for b in boxes), gap=int(median_w * 0.5))
    rows = _cluster(sorted(b.y for b in boxes), gap=int(median_h * 0.5))
    if not cols or not rows:
        return ContourGrid(tuple(boxes), tuple(rows), tuple(cols))

    def nearest(value: int, centres: list[int]) -> int:
        return min(range(len(centres)), key=lambda i: abs(centres[i] - value))

    occupancy: dict[int, set[int]] = {i: set() for i in range(len(cols))}
    for b in boxes:
        occupancy[nearest(b.x, cols)].add(nearest(b.y, rows))

    best = max((len(v) for v in occupancy.values()), default=0)
    keep = {i for i, v in occupancy.items() if len(v) >= best * MIN_COLUMN_OCCUPANCY}
    cols = [c for i, c in enumerate(cols) if i in keep]
    boxes = [b for b in boxes if nearest(b.x, cols) is not None and
             min(abs(c - b.x) for c in cols) <= median_w * 0.5] if cols else boxes

    if len(cols) < MIN_COLUMNS:
        return ContourGrid((), (), ())
    return ContourGrid(tuple(boxes), tuple(rows), tuple(cols))
