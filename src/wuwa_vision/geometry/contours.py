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
median width filter -> height filter against the tallest row -> drop frame-edge boxes.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

__all__ = ["TileBox", "ContourGrid", "detect_boxes", "detect_grid"]

CANNY_LO, CANNY_HI = 40, 120
MIN_AREA = 3000
ASPECT_LO, ASPECT_HI = 0.6, 1.1
#: Boxes whose size deviates more than this from a whole tile's are not tiles.
SIZE_TOLERANCE = 0.25
#: Boxes touching the frame edge are clipped tiles; their crops would be partial.
EDGE_MARGIN = 5
#: A box this much shorter than a whole tile is a row clipped by the SCROLL VIEW, not
#: the frame edge: the view masks tiles mid-grid, so EDGE_MARGIN never sees them.
#: Its bar and count are cut off, so it reads as 1-star with no count, and those
#: ghosts broke the next frame's registration: it placed the same row one pitch
#: lower as six new items. Live ghost: 0.75. Measured on fixtures and captures:
#: clipped rows 0.77-0.89, real tiles never below 0.93 (1-star flower rows).
MAX_SHORTFALL = 0.09
#: Inside that margin (D253): a whole tile fills at least 0.817 of the rows' spacing on every
#: fixture and view, and a row cut to 0.95 of a tile 0.808.
MIN_ROW_FILL = 0.813
#: An edge in its place is at least 0.962 of the largest spacing in its frame, a cut one 0.948.
MIN_EDGE_SPACING = 0.955
#: A tile is at least this tall relative to the WINDOW (a ratio, not a pixel size,
#: so it holds at any resolution). Needed because the size filter below is relative
#: to the boxes found: on a frame with no grid (mid tab switch, grid still drawing)
#: the left-rail tab icons are the majority, set the height, and were read as items.
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
    height = rgb.shape[0]
    wide = [b for b in candidates if abs(b.w - median_w) <= median_w * SIZE_TOLERANCE]
    if not wide:
        return []
    tile_h = _whole_tile_height(wide, median_w)

    keep: list[TileBox] = []
    for b in wide:
        if abs(b.h - tile_h) > tile_h * SIZE_TOLERANCE:
            continue
        if b.h < tile_h * (1.0 - MAX_SHORTFALL):
            continue
        if b.y <= EDGE_MARGIN or b.y + b.h >= height - EDGE_MARGIN:
            continue
        keep.append(b)
    return _without_slightly_cut_rows(keep, median_w)


def _rows_of(boxes: list[TileBox], median_w: float) -> list[list[TileBox]]:
    """The boxes in their rows, top to bottom."""
    tops = _cluster(sorted(b.y for b in boxes), gap=int(median_w * 0.5))
    rows: dict[int, list[TileBox]] = {}
    for b in boxes:
        rows.setdefault(min(tops, key=lambda t: abs(t - b.y)), []).append(b)
    return [rows[top] for top in sorted(rows)]


def _whole_tile_height(boxes: list[TileBox], median_w: float) -> float:
    """The height of a whole tile: that of the tallest row (D250).

    Not the median of every box: a view can hold two cut rows and two whole ones, and the median
    of those is no tile's height. The scroll view only ever makes a row shorter, so the tallest
    is whole. A row is MIN_COLUMNS boxes or more, so that one selected tile or the panel's big
    picture is not one. Falls back to the median over all boxes when no row has that many.
    """
    heights = [float(np.median([b.h for b in row])) for row in _rows_of(boxes, median_w)
               if len(row) >= MIN_COLUMNS]
    if not heights:
        return float(np.median([b.h for b in boxes]))
    return max(heights)


def _without_slightly_cut_rows(boxes: list[TileBox], median_w: float) -> list[TileBox]:
    """Drop a first or last row cut by less than MAX_SHORTFALL (D253).

    Height alone cannot tell it from a row with nothing standing out of its tiles, so a row must
    also have moved: the scroll view takes the top off a first row and the bottom off a last one,
    and that edge then stands closer to the next row's than the rows' own spacing. Three rows at
    least: one gap measures nothing. Only the outer rows, since only they meet the view's edges.
    """
    rows = [row for row in _rows_of(boxes, median_w) if len(row) >= MIN_COLUMNS]
    if len(rows) < 3:
        return boxes
    top_gaps = np.diff([float(np.median([b.y for b in row])) for row in rows])
    end_gaps = np.diff([float(np.median([b.y + b.h for b in row])) for row in rows])
    least = float(top_gaps.max()) * MIN_ROW_FILL

    def short(row: list[TileBox]) -> bool:
        return float(np.median([b.h for b in row])) < least

    cut: list[TileBox] = []
    if short(rows[0]) and top_gaps[0] < top_gaps.max() * MIN_EDGE_SPACING:
        cut += rows[0]
    if short(rows[-1]) and end_gaps[-1] < end_gaps.max() * MIN_EDGE_SPACING:
        cut += rows[-1]
    return [b for b in boxes if b not in set(cut)]


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
#: A real column stands one pitch from the next. The panel's big picture of the selected
#: item stands off to the right of the grid, and with two rows on screen one tile is half
#: of them, so it is not sparse (D244). 1.5: a column missed whole is two pitches away.
MAX_COLUMN_GAP = 1.5


def _without_a_column_far_off(cols: list[int]) -> list[int]:
    """Drop the last column when it stands well past the pitch of the others (D244)."""
    if len(cols) < 3:
        return cols
    pitch = min(b - a for a, b in zip(cols, cols[1:], strict=False))
    return cols[:-1] if cols[-1] - cols[-2] > pitch * MAX_COLUMN_GAP else cols


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
    cols = _without_a_column_far_off([c for i, c in enumerate(cols) if i in keep])
    boxes = [b for b in boxes if nearest(b.x, cols) is not None and
             min(abs(c - b.x) for c in cols) <= median_w * 0.5] if cols else boxes
    # what went with a column may have been a row of its own: it would number the rest wrong
    rows = _cluster(sorted(b.y for b in boxes), gap=int(median_h * 0.5))

    if len(cols) < MIN_COLUMNS:
        return ContourGrid((), (), ())
    return ContourGrid(tuple(boxes), tuple(rows), tuple(cols))
