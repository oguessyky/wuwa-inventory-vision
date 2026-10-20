# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""OCR: RapidOCR (PP-OCR models under ONNXRuntime), CPU by default.

Why CPU (PLAN.md D11): GPU OCR saves only a few seconds per scan, while a second
CUDA runtime would contend for VRAM with the game and with torch. One CUDA
framework in the process: torch.

The engine is lazily constructed so importing this module -- and running the
geometry tests -- never pays the model-load cost.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

import numpy as np

_DIGITS = re.compile(r"\d+")


@lru_cache(maxsize=1)
def _engine() -> Any:
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def available() -> bool:
    try:
        _engine()
    except Exception:
        return False
    return True


def read_text(crop: np.ndarray) -> list[tuple[str, float]]:
    """Return [(text, confidence)] for a small RGB crop."""
    if crop.size == 0:
        return []
    result, _ = _engine()(crop)
    if not result:
        return []
    return [(str(line[1]), float(line[2])) for line in result]


def read_boxes(crop: np.ndarray) -> list[tuple[float, str, float]]:
    """Return [(left x, text, confidence)] -- for reading several values in one strip."""
    if crop.size == 0:
        return []
    result, _ = _engine()(crop)
    if not result:
        return []
    return [(float(min(p[0] for p in line[0])), str(line[1]), float(line[2])) for line in result]


def read_line(crop: np.ndarray) -> tuple[str, float]:
    """Recognition ONLY -- no detection stage. Returns (text, confidence).

    The count's position is already known from the fitted lattice, so running
    detection is both wasted work and actively harmful: PP-OCR's detector splits
    a number into per-digit boxes in arbitrary order (observed: 4113 -> 41, 1, 3),
    which silently truncates counts.
    """
    if crop.size == 0:
        return ("", 0.0)
    out = _engine()(crop, use_det=False, use_cls=False, use_rec=True)
    result = out[0] if isinstance(out, tuple) else out
    if not result:
        return ("", 0.0)
    first = result[0]
    if isinstance(first, (list, tuple)) and len(first) >= 2:
        return (str(first[0]), float(first[1]))
    return (str(first), 0.0)


def _upscale(crop: np.ndarray, factor: int = 3) -> np.ndarray:
    return _stretch(crop, factor)


def _stretch(crop: np.ndarray, factor: int = 3, wider: float = 1.0) -> np.ndarray:
    from PIL import Image as _Image

    h, w = crop.shape[:2]
    return np.asarray(
        _Image.fromarray(crop).resize((int(w * factor * wider), h * factor), _Image.LANCZOS)
    )


def digit_glyphs(crop: np.ndarray) -> int:
    """How many digits a count crop shows, counted from its white glyphs rather than read (D170).

    The digits are white; the rarity bar along the top is coloured and the tile's art is not
    white, so only near-white pixels count. Pieces that overlap sideways are one glyph. It can
    count too FEW (two digits or a light background running together), never too many, which is
    the direction the reader goes wrong in.
    """
    if crop.size == 0:
        return 0
    import cv2

    lo = crop.min(axis=2).astype(int)
    hi = crop.max(axis=2).astype(int)
    white = ((lo > 160) & (hi - lo < 50)).astype(np.uint8)
    _, _, stats, _ = cv2.connectedComponentsWithStats(white, connectivity=8)
    parts = [s for s in stats[1:] if s[4] >= 6]
    if not parts:
        return 0
    tall = max(int(s[3]) for s in parts)
    glyphs: list[list[int]] = []
    for s in sorted((s for s in parts if s[3] >= 0.6 * tall), key=lambda s: int(s[0])):
        left, right = int(s[0]), int(s[0] + s[2])
        if glyphs and left < glyphs[-1][1] - 1:
            glyphs[-1][1] = max(glyphs[-1][1], right)
        else:
            glyphs.append([left, right])
    return len(glyphs)


#: How much wider a count is drawn for the second reading, when the first lost a digit (D170).
SPREAD = (1.5, 2.0)
#: The confidence a read is left with when it is known to be short and nothing better was found.
SHORT = 0.5


def read_count(crop: np.ndarray) -> tuple[int | None, float]:
    """Read a stack count. Returns (value, confidence); value is None if unread.

    Counts reach five digits (63783 observed), so no width is assumed. A low
    confidence is never silently promoted -- the caller queues a hover fallback
    against the detail panel's `拥有 N`, which is an independent oracle (D11).

    A digit repeated side by side can be lost (D170): the recogniser's CTC decoding merges
    a run of the same character, and the game's digits sit close (444 read 44 at 0.99).
    When the crop shows more white glyphs than the read has digits, the count is read again
    drawn wider, which gives each digit room; both wider readings must agree and have one
    digit per glyph to be taken. Otherwise the short read stays, marked unsure.
    """
    text, conf = read_line(_upscale(crop))
    digits = "".join(_DIGITS.findall(text))
    if not digits:
        return (None, 0.0)
    if text.strip().isdigit():
        shown = digit_glyphs(crop)
        if shown > len(digits):
            wider = [read_line(_stretch(crop, wider=w)) for w in SPREAD]
            said = {w[0].strip() for w in wider}
            if len(said) == 1 and (again := said.pop()).isdigit() and len(again) == shown:
                return (int(again), min(w[1] for w in wider))
            return (int(digits), min(conf, SHORT))
    return (int(digits), conf)


#: A count read at least this well is kept without trying the alternative crops.
GOOD_COUNT = 0.90


def read_tile_count(
    crop: np.ndarray, alternatives: tuple[np.ndarray, ...] = ()
) -> tuple[int | None, float]:
    """`read_count`, retrying nearby crops when the usual one reads badly.

    Only a missing or weak read (< GOOD_COUNT) is revisited, and the most
    confident read wins -- so a good read never changes and a guess is never
    promoted over a clean read.
    """
    best = read_count(crop)
    for alt in alternatives:
        if best[0] is not None and best[1] >= GOOD_COUNT:
            break
        read = read_count(alt)
        if read[0] is not None and read[1] > best[1]:
            best = read
    return best
