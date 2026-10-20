# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Tile extraction: turn a fitted lattice into per-tile regions and reads.

Tile anatomy, measured against fixtures rather than assumed:

    origin.y + 0.00 * extent   tile top
    origin.y + 0.05 * extent   icon artwork begins
    origin.y + 0.88 * extent   icon artwork ends
    origin.y + 0.93 * extent   rarity bar begins   (absent for 1-star)
    origin.y + 1.00 * extent   rarity bar ends / lattice box ends
    origin.y + 1.00 * pitch    next tile top

The lattice's two-peak fold locks onto (tile top, rarity bar), so `extent` stops
at the bar and the count footer falls in what looks like the inter-tile gap.
The count therefore lives in [origin.y + extent, origin.y + pitch].
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from ..geometry.contours import detect_grid
from ..geometry.lattice import Lattice, fit_lattice
from .rarity import RarityRead, classify

ICON_TOP, ICON_BOTTOM = 0.05, 0.88
BAR_TOP, BAR_BOTTOM = 0.93, 0.995
#: Counts are right-aligned in the footer; skip the left half to avoid badges.
COUNT_LEFT = 0.40
#: Trim the rounded corners before sampling the bar.
BAR_INSET = 0.20
#: A contour this much larger than the median in BOTH axes is a selection outline.
OUTLINE_GROWTH = 1.03
#: Lattice fold quality below which the fit is not a grid (see Axis.quality).
MIN_LATTICE_QUALITY = 2.5
#: Accepted column/row pitch ratio for a lattice fit (measured 0.83 on every
#: fixture, 21:9 and 3:2 alike).
PITCH_RATIO = (0.78, 0.88)
#: Accepted tile width/height for a lattice fit (fixtures: 0.79-1.01). The live
#: tab-switch slivers were ~0.55.
EXTENT_RATIO = (0.65, 1.10)


@dataclass(frozen=True, slots=True)
class Tile:
    """One extracted grid cell."""

    row: int
    col: int
    box: tuple[int, int, int, int]
    icon: np.ndarray
    """RGB crop of the artwork area -- what the embedding will consume."""
    count_crop: np.ndarray
    """RGB crop of the count footer -- what OCR will consume."""
    rarity: RarityRead
    count_alts: tuple[np.ndarray, ...] = ()
    """The footer a little higher / lower, tried only when `count_crop` reads badly."""
    rank_crop: np.ndarray | None = None
    """武器 layout: the 谐振阶数, which sits INSIDE the artwork (D61)."""
    rank_alts: tuple[np.ndarray, ...] = ()
    level_crop: np.ndarray | None = None
    """武器 layout: the "Lv. 90" footer, where a bag tile has its count."""
    holder_crop: np.ndarray | None = None
    """武器 layout: the portrait of whoever is carrying it, top-left corner."""

    @property
    def key(self) -> tuple[int, int]:
        return (self.row, self.col)


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def extract(rgb: np.ndarray, lattice: Lattice) -> list[Tile]:
    """Extract every full tile the lattice describes.

    Partial tiles (clipped by the frame edge) are skipped: a half-read count is
    worse than no count, and cross-frame stitching will catch them at another
    scroll offset.
    """
    h, w = rgb.shape[:2]
    extent = lattice.rows.extent
    pitch = lattice.rows.pitch
    tiles: list[Tile] = []

    for r in range(lattice.rows.count):
        for c in range(lattice.cols.count):
            x0, y0, x1, y1 = lattice.box(r, c)
            footer_bottom = int(round(y0 + pitch * 0.97))
            if x1 > w or footer_bottom > h or x0 < 0 or y0 < 0:
                continue

            icon = rgb[
                _clamp(y0 + int(extent * ICON_TOP), 0, h) : _clamp(
                    y0 + int(extent * ICON_BOTTOM), 0, h
                ),
                x0:x1,
            ]

            inset = int((x1 - x0) * BAR_INSET)
            bar = rgb[
                _clamp(y0 + int(extent * BAR_TOP), 0, h) : _clamp(
                    y0 + int(extent * BAR_BOTTOM), 0, h
                ),
                x0 + inset : x1 - inset,
            ]

            count_crop = rgb[
                _clamp(y0 + extent, 0, h) : _clamp(footer_bottom, 0, h),
                x0 + int((x1 - x0) * COUNT_LEFT) : x1,
            ]

            if icon.size == 0 or count_crop.size == 0:
                continue

            # The lattice box stops at the rarity bar; the 武器 crops are
            # fractions of the whole tile, so scale its height back up first.
            rank_crop, rank_alts, level, holder = _weapon_crops(
                rgb, x0, y0, x1 - x0, int(round(extent / EXTENT_OF_BOX))
            )
            tiles.append(
                Tile(
                    row=r,
                    col=c,
                    box=(x0, y0, x1, y1),
                    icon=icon,
                    count_crop=count_crop,
                    rarity=classify(bar),
                    rank_crop=rank_crop,
                    rank_alts=rank_alts,
                    level_crop=level,
                    holder_crop=holder,
                )
            )
    return tiles


# --------------------------------------------------------------------------
# Contour path (primary)
#
# A contour box is the WHOLE tile panel -- icon, rarity bar AND count footer
# inside one rounded rectangle. That differs from the lattice box, which stops at
# the rarity bar and leaves the count in what looks like the inter-tile gap. So
# these fractions are of the BOX height, and are self-contained: no pitch needed.
#
# Measured on res_21_9_a box0 (y=315 h=263; count "4113" at y 527-565), then tuned
# over all 257 detected tiles across the fixture set.
# --------------------------------------------------------------------------

# 0.74, not 0.66: at 0.66 the artwork is visibly clipped (ring bases, star tips
# cut off). The artwork runs down to just above the rarity bar at 0.75, and 0.76
# starts bleeding the bar's colour into the crop. A clipped crop is not only ugly
# on the page -- it also embeds worse.
BOX_ICON_TOP, BOX_ICON_BOTTOM = 0.04, 0.74
BOX_BAR_TOP, BOX_BAR_BOTTOM = 0.75, 0.80
BOX_COUNT_TOP, BOX_COUNT_BOTTOM = 0.78, 0.96
BOX_COUNT_LEFT = 0.50
#: Where else to read the count when the usual crop reads nothing or reads weakly,
#: as fractions of box height. A lone digit is fragile: on fixtures a "7" read at
#: 0.62, and at 2% higher or lower read nothing at all -- live, a selected tile's
#: box sat a few px off and its "7" never read, so the panel never attached (D37).
COUNT_SEARCH = (0.02, -0.02, 0.04)


# --------------------------------------------------------------------------
# The 武器 tab's own tile layout (D61), as fractions of the CONTOUR box.
#
# A weapon tile is not a bag tile. Weapons never stack -- each copy is its own
# tile, with its own level and 谐振阶数 -- so the number above the rarity bar is
# that copy's RANK (1-5), not a count, the footer holds "Lv. 90" where a bag tile
# holds its count, and the top-left corner carries the portrait of whoever has it
# equipped. Read as a bag tile, the tab stored the LEVEL as the count: 122 weapons
# "owned 90" (D61, D63).
#
# Measured on train_dataset wuwa_weapon_1..4 (2560x1600, 200x247 boxes): count
# 0.61-0.71, lock icon 0.43-0.55, rarity bar 0.76-0.81, "Lv. 90" 0.84-0.94,
# portrait frame 0.03-0.26 of the width. The crops below sit inside those.
# --------------------------------------------------------------------------

#: Left edge 0.72, not 0.60: the artwork behind the number added digits of its own
#: (a "1" read as 21, a "5" as 75) until the crop stopped at the number itself.
WEAPON_RANK = (0.60, 0.74, 0.72)
"""(top, bottom, left) of the 谐振阶数."""
WEAPON_LEVEL = (0.80, 0.98, 0.45)
"""(top, bottom, left) of the "Lv. 90" footer."""
# The portrait is found, not assumed (D95). A contour box is the tile PLUS
# whatever sticks out of it -- the portrait's own frame top-left, a 新 badge
# top-right, the gold outline of the selected tile -- so the same tile is boxed
# 208, 214 or 220 px wide at 3440x1440, and a fixed fraction of that box landed
# on a different part of the face each time. The frame is a light grey rounded
# square; it is located by its outline and the crop is taken inside it.
PORTRAIT_SIDE = (0.23, 0.275)
"""The frame's side as a fraction of the median tile width (measured 0.24-0.255
at 2560x1600, 0.25 at 3440x1440)."""
PORTRAIT_SEARCH = (-0.10, 0.42)
"""Where the frame's box may lie, from the tile's corner, in tile widths."""
PORTRAIT_GREY = (150, 80)
"""The outline's colour: at least this bright (V), at most this saturated (S)."""
PORTRAIT_FOUND = 0.70
"""Share of the outline that must be there. Fixtures: 0.84-1.00 with a portrait,
0.50 at most without one."""
PORTRAIT_INSET = 0.10
"""Cut this far inside the frame -- its border is the same for everyone and only
dilutes the match."""
#: The lattice's `extent` stops at the rarity bar (BAR_TOP of the extent), which
#: is BOX_BAR_TOP of the whole tile: that ratio converts one to the other.
EXTENT_OF_BOX = BOX_BAR_TOP / BAR_TOP


def _outline(side: int) -> np.ndarray:
    """A rounded square's outline, `side` px across: what a portrait frame looks like."""
    ring = np.zeros((side, side), np.float32)
    cv2.rectangle(ring, (0, 0), (side - 1, side - 1), 1.0, 2)
    r = max(3, int(side * 0.14))  # the rounded corners: not counted either way
    ring[:r, :r] = ring[:r, -r:] = ring[-r:, :r] = ring[-r:, -r:] = 0.0
    return ring


def locate_portrait(
    rgb: np.ndarray, x: int, y: int, tile_w: int
) -> tuple[int, int, int] | None:
    """(x, y, side) of the holder's portrait frame at a tile's top-left, or None.

    None means nobody is carrying the weapon: the frame is only drawn when
    someone is. `tile_w` is the grid's median tile width, not this box's own --
    the box grows with whatever sticks out of the tile.
    """
    lo, hi = PORTRAIT_SEARCH
    x0, y0 = max(x + int(tile_w * lo), 0), max(y + int(tile_w * lo), 0)
    window = rgb[y0 : y + int(tile_w * hi), x0 : x + int(tile_w * hi)]
    if window.size == 0:
        return None
    hsv = cv2.cvtColor(np.ascontiguousarray(window), cv2.COLOR_RGB2HSV)
    bright, grey = PORTRAIT_GREY
    mask = ((hsv[..., 2] >= bright) & (hsv[..., 1] <= grey)).astype(np.float32)
    best, found = PORTRAIT_FOUND, None
    for side in range(int(tile_w * PORTRAIT_SIDE[0]), int(tile_w * PORTRAIT_SIDE[1]) + 1):
        if side < 8 or side > min(mask.shape):
            continue
        ring = _outline(side)
        hits = cv2.matchTemplate(mask, ring, cv2.TM_CCORR) / float(ring.sum())
        _, score, _, (px, py) = cv2.minMaxLoc(hits)
        if score > best:
            best, found = score, (x0 + px, y0 + py, side)
    return found


def _weapon_crops(
    rgb: np.ndarray, x: int, y: int, w: int, h: int, tile_w: int | None = None
) -> tuple[np.ndarray | None, tuple[np.ndarray, ...], np.ndarray | None, np.ndarray | None]:
    """The 武器 layout's three extra crops for one tile box (rank, level, holder)."""
    h_img, w_img = rgb.shape[:2]

    def cut(top: float, bottom: float, left: float, right: float = 1.0) -> np.ndarray:
        return rgb[
            _clamp(y + int(h * top), 0, h_img) : _clamp(y + int(h * bottom), 0, h_img),
            _clamp(x + int(w * left), 0, w_img) : _clamp(x + int(w * right), 0, w_img),
        ]

    top, bottom, left = WEAPON_RANK
    rank = cut(top, bottom, left)
    alts = tuple(
        crop for shift in COUNT_SEARCH
        if (crop := cut(top + shift, bottom + shift, left)).size
    )
    level = cut(*WEAPON_LEVEL)
    holder = None
    frame = locate_portrait(rgb, x, y, tile_w or w)
    if frame is not None:
        fx, fy, side = frame
        inset = max(2, int(round(side * PORTRAIT_INSET)))
        holder = rgb[fy + inset : fy + side - inset, fx + inset : fx + side - inset]
    return (
        rank if rank.size else None,
        alts,
        level if level.size else None,
        holder if holder is not None and holder.size else None,
    )



def extract_contours(rgb: np.ndarray) -> list[Tile]:
    """Extract tiles from per-tile contour boxes.

    Preferred over the lattice: on the fixture set it finds 257 tiles to the
    lattice's 213 (+21%) and yields 253 confident counts to 208, because it tracks
    each tile's own rectangle instead of deriving every box from one global fit.
    """
    grid = detect_grid(rgb)
    if not grid.boxes:
        return []

    h_img, w_img = rgb.shape[:2]
    cols = list(grid.cols)
    rows = list(grid.rows)
    tiles: list[Tile] = []
    med_w = int(np.median([b.w for b in grid.boxes]))
    med_h = int(np.median([b.h for b in grid.boxes]))

    for b in grid.boxes:
        x, y, w, h = b.x, b.y, b.w, b.h
        if w > med_w * OUTLINE_GROWTH and h > med_h * OUTLINE_GROWTH:
            # The selected tile's contour is its gold OUTLINE, ~6-10% larger than
            # the tile. Reading crops off it shifted them: the count read at 0.86
            # instead of ~1.0 and the rarity bar was missed (5* read as 1*), which
            # let a panel read land on the wrong tile (D32). Use a tile-sized box
            # centred in the outline.
            x += (w - med_w) // 2
            y += (h - med_h) // 2
            w, h = med_w, med_h
        if y + int(h * BOX_COUNT_BOTTOM) > h_img or x + w > w_img:
            continue

        icon = rgb[y + int(h * BOX_ICON_TOP) : y + int(h * BOX_ICON_BOTTOM), x : x + w]
        count_crop = rgb[
            y + int(h * BOX_COUNT_TOP) : y + int(h * BOX_COUNT_BOTTOM),
            x + int(w * BOX_COUNT_LEFT) : x + w,
        ]
        if icon.size == 0 or count_crop.size == 0:
            continue
        alts = []
        for shift in COUNT_SEARCH:
            d = int(round(h * shift))
            top = y + int(h * BOX_COUNT_TOP) + d
            bottom = min(y + int(h * BOX_COUNT_BOTTOM) + d, h_img)
            alt = rgb[top:bottom, x + int(w * BOX_COUNT_LEFT) : x + w]
            if alt.size:
                alts.append(alt)

        # Nearest detected row/column, so downstream keys stay grid-shaped.
        r = min(range(len(rows)), key=lambda i: abs(rows[i] - y)) if rows else 0
        c = min(range(len(cols)), key=lambda i: abs(cols[i] - x)) if cols else 0

        rank_crop, rank_alts, level, holder = _weapon_crops(rgb, x, y, w, h, med_w)
        tiles.append(
            Tile(
                row=r,
                col=c,
                box=(x, y, x + w, y + h),
                icon=icon,
                count_crop=count_crop,
                rarity=_read_rarity(rgb, (x, y, w, h)),
                count_alts=tuple(alts),
                rank_crop=rank_crop,
                rank_alts=rank_alts,
                level_crop=level,
                holder_crop=holder,
            )
        )
    return tiles


#: Where else to look for the bar when the usual strip finds none, as fractions of
#: box height. Live, a few boxes came out ~7 px taller than their row (241 vs 234
#: px) and the strip slid off the bar: three 5-star tiles read as 1-star (D33).
BAR_SEARCH = (-0.02, 0.02, -0.04, 0.04)


def _read_rarity(rgb: np.ndarray, box: tuple[int, int, int, int]):  # -> RarityRead
    """Classify the rarity bar, searching nearby only when the usual strip is empty.

    Only a "no bar" (1-star) answer is ever revisited, and only a confident 2-5 read
    replaces it -- so a correct read never changes. Over 884 fixture and capture
    tiles this changed exactly 8, all 1 -> 5 and all real gold bars.
    """
    x, y, w, h = box
    inset = int(w * BAR_INSET)

    def strip(shift: float) -> np.ndarray:
        d = int(round(h * shift))
        return rgb[
            y + int(h * BOX_BAR_TOP) + d : y + int(h * BOX_BAR_BOTTOM) + d,
            x + inset : x + w - inset,
        ]

    read = classify(strip(0.0))
    if read.rarity != 1:
        return read
    for shift in BAR_SEARCH:
        alt = classify(strip(shift))
        if alt.rarity >= 2 and alt.confidence >= 0.5:
            return alt
    return read


def detect_tiles(rgb: np.ndarray, grey: np.ndarray | None = None) -> tuple[list[Tile], str]:
    """Extract tiles, preferring contours and falling back to the lattice.

    The two methods fail on different frames, so the fallback is real cover rather
    than ceremony: contours recover the low-contrast edge column the lattice prunes,
    while the lattice still fits when contrast is too low for Canny to close a box.
    """
    tiles = extract_contours(rgb)
    if tiles:
        return tiles, "contour"
    if grey is None:
        grey = (
            0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
        ).astype(np.float32)
    lattice = fit_lattice(grey)
    # The lattice ALWAYS returns a grid, even on a frame with no grid at all (a tab
    # switch, the grid still drawing): there it invented 80 tiles. Its own quality
    # score says when to believe it -- real grids fold at 3.6-12.1, a blank 0.0 (D27).
    if min(lattice.rows.quality, lattice.cols.quality) < MIN_LATTICE_QUALITY:
        return [], "none"
    # The grid's shape is fixed by the game: column pitch / row pitch is 0.83 on
    # every capture, 21:9 and 3:2 alike. Live, a tab-switch animation frame passed
    # the quality check as a 4x15 grid of 96 px slivers and added 60 blank "items"
    # (D33). A squashed or stretched fit is not the grid.
    ratio = lattice.cols.pitch / max(lattice.rows.pitch, 1e-6)
    aspect = lattice.cols.extent / max(lattice.rows.extent, 1)
    if not (
        PITCH_RATIO[0] <= ratio <= PITCH_RATIO[1]
        and EXTENT_RATIO[0] <= aspect <= EXTENT_RATIO[1]
    ):
        return [], "none"
    return extract(rgb, lattice), "lattice"
