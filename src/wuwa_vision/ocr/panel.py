# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""The detail panel: the selected item's Chinese name and the game's own count.

Right of the grid the game shows, for the selected tile:

    特级密音筒          <- name
    声骸养成材料        <- category
    拥有 1125           <- owned: the authoritative quantity

A weapon's panel has no 拥有 -- weapons are not a quantity -- and prints instead:

    赝作的矮星          <- name
    音感仪              <- category
    等级 90/90          <- level: what proves the panel is about the selected tile
    1阶 寂静            <- the 谐振阶数, the number that tile shows
    达妮娅装配中        <- the holder, in the game's own words (read separately)

This is the hover bootstrap of D3/D17 done passively (D24): the USER clicks a
tile, and this reads what the game prints about it. No input is sent.

No pixel constants: the panel is located as "right of the rightmost tile" and
"above the lower half of the window", then read with text DETECTION on, because
the layout differs between 21:9 and 16:10. Lines are identified by content, not
position -- `拥有` anchors the count, and the name is the first CJK line above it
(the currency counters in the same strip are digits only).

The panel never contains the UID (it sits bottom-right, below this crop). The
crop is written only to the local run record (scan/recorder.py, D38).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

from .engine import _engine

_OWNED = re.compile(r"拥有\s*[:：]?\s*(\d+)")
#: "等级 90/90" -- a weapon panel's own cross-check against the tile's "Lv. 90".
_LEVEL = re.compile(r"等级\s*[:：]?\s*(\d{1,3})\s*/\s*(\d{1,3})")
#: "1阶 寂静": the 谐振阶数 the tile also shows.
_RANK = re.compile(r"(?<!\d)([1-5])\s*阶")
#: "达妮娅装配中": who has this weapon equipped, in the game's own words (D64).
_HOLDER = re.compile(r"([一-鿿·]{2,10})\s*装\s*配\s*中")
#: The panel's name/category/owned block sits in the upper part of the window.
PANEL_BOTTOM = 0.50
#: A CJK line read below this confidence cannot be the name or category.
MIN_LINE_CONFIDENCE = 0.60
#: Skip the grid's scrollbar: start this many tile widths right of the last tile.
PANEL_GAP_TILES = 0.25


@dataclass(frozen=True, slots=True)
class Panel:
    name: str
    category: str | None
    owned: int | None
    confidence: float
    level: int | None = None
    """武器: 等级 N/M -- what a weapon panel has instead of a count (D64)."""
    rank: int | None = None
    """武器: the 谐振阶数, from the "N阶" line."""
    holder: str | None = None
    """武器: who has it equipped, from "X装配中" (read_holder, D64)."""


def _has_cjk(text: str) -> bool:
    return any("一" <= ch <= "鿿" for ch in text)


def crop_panel(
    rgb: np.ndarray, tile_boxes: list[tuple[int, int, int, int]],
    top: float = 0.0, bottom: float = PANEL_BOTTOM,
) -> np.ndarray:
    h = rgb.shape[0]
    right = max(b[2] for b in tile_boxes)
    width = float(np.median([b[2] - b[0] for b in tile_boxes]))
    return rgb[int(h * top) : int(h * bottom), int(right + PANEL_GAP_TILES * width) :]


def parse_lines(lines: list[tuple[float, str, float]]) -> Panel | None:
    """Pick name / category / owned out of (y, text, confidence) lines."""
    lines = sorted(lines)
    owned_at = None
    owned = None
    owned_conf = 0.0
    for i, (_, text, conf) in enumerate(lines):
        m = _OWNED.search(text.replace(" ", ""))
        if m:
            owned_at, owned, owned_conf = i, int(m.group(1)), conf
            break
    above = lines[:owned_at] if owned_at is not None else lines
    # Weak fragments are not the name: live, a stray 永 (0.36) read off the
    # currency strip above the panel was taken as the name of 声匣 (0.95), and
    # the read was then dropped for its low confidence (D39).
    cjk = [(t.strip(), c) for _, t, c in above if _has_cjk(t) and c >= MIN_LINE_CONFIDENCE]
    if not cjk:
        return None
    name, name_conf = cjk[0]
    # Category lines can carry a trailing badge glyph read as "+" (药品+).
    category = cjk[1][0].rstrip("+＋ ") if len(cjk) > 1 else None
    # The COUNT decides whether a read is trusted: it must also equal the selected
    # tile's own count to attach (D32), which is what proves the panel is about
    # that tile. The name only has to clear MIN_LINE_CONFIDENCE: OCR confidence
    # says little about a name's correctness -- 改造镣环 read as 改造环 at 1.00,
    # while 梦魇炽枢 (0.71) and 傀儡的秽冕 (0.76) were dropped with their counts (D39).
    confidence = owned_conf if owned is not None else name_conf
    flat = [t.replace(" ", "") for _, t, _ in lines]
    level = next((int(m.group(1)) for t in flat if (m := _LEVEL.search(t))), None)
    rank = next((int(m.group(1)) for t in flat if (m := _RANK.search(t))), None)
    return Panel(name=name, category=category, owned=owned, confidence=confidence,
                 level=level, rank=rank)


def read_panel(
    rgb: np.ndarray,
    tile_boxes: list[tuple[int, int, int, int]],
    lines_out: list[tuple[float, str, float]] | None = None,
) -> Panel | None:
    """Read the detail panel, or None when there is no readable panel.

    `lines_out`, when given, receives the raw OCR lines -- the run record keeps
    them for reads that failed.
    """
    if not tile_boxes:
        return None
    crop = crop_panel(rgb, tile_boxes)
    if crop.size == 0:
        return None
    lines = _read_down_to_owned(crop)
    if not lines:
        return None
    if lines_out is not None:
        lines_out.extend(lines)
    return parse_lines(lines)


#: Where a weapon panel's "X装配中" line sits, as fractions of the window height.
#: Below the description paragraph, which is the expensive part to read -- so it
#: is read as a strip of its own rather than by extending the panel crop (D64).
HOLDER_STRIP = (0.62, 0.92)


def read_holder(rgb: np.ndarray, tile_boxes: list[tuple[int, int, int, int]]) -> str | None:
    """The name in "X装配中" under a weapon panel, or None (D64).

    The game's own words about who is carrying the selected weapon: worth a
    second small OCR pass, because it NAMES a portrait instead of guessing at it.
    """
    if not tile_boxes:
        return None
    crop = crop_panel(rgb, tile_boxes, *HOLDER_STRIP)
    if crop.size == 0:
        return None
    for _, text, conf in _read_down_to_owned(crop):
        if conf < MIN_LINE_CONFIDENCE:
            continue
        match = _HOLDER.search(text.replace(" ", ""))
        if match:
            return match.group(1)
    return None


#: Pixels kept around a detected line before recognising it on its own.
LINE_PAD = 2


def _read_down_to_owned(crop: np.ndarray) -> list[tuple[float, str, float]]:
    """(y, text, confidence) per line, top down, stopping at the `拥有` line.

    Detection runs on the whole crop (the layout differs between 21:9, 16:10 and
    3:2, so no fixed sub-crop holds 拥有 everywhere), but recognition stops once
    `拥有` is read: the description paragraphs below it were most of the cost.
    Measured on 27 panels across all three layouts: 0.84 s vs 2.1 s, identical
    name and count on every one (D39).
    """
    engine = _engine()
    boxes, _ = engine(crop, use_det=True, use_cls=False, use_rec=False)
    if not boxes:
        return []
    h, w = crop.shape[:2]
    lines: list[tuple[float, str, float]] = []
    for box in sorted(boxes, key=lambda b: min(pt[1] for pt in b)):
        pts = np.asarray(box)
        x0, y0 = (int(v) for v in pts.min(axis=0))
        x1, y1 = (int(v) for v in pts.max(axis=0))
        line = crop[max(y0 - LINE_PAD, 0) : min(y1 + LINE_PAD, h),
                    max(x0 - LINE_PAD, 0) : min(x1 + LINE_PAD, w)]
        if line.size == 0:
            continue
        out, _ = engine(line, use_det=False, use_cls=False, use_rec=True)
        if not out:
            continue
        text, conf = str(out[0][0]), float(out[0][1])
        lines.append((float(y0), text, conf))
        if _OWNED.search(text.replace(" ", "")):
            break
    return lines
