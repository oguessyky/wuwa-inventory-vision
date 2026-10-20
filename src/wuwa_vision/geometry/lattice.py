# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Periodic lattice fitting for the inventory grid.

The grid is a regular lattice of tiles, but nothing about it may be hard-coded:
the user runs 3440x1440 (21:9, 9 columns) and 2560x1600 (16:10), and a 2940x1912
(3:2) capture renders only 6 columns. Pitch, phase, tile extent and column count
are all derived per scan. See PLAN.md D7/D9.

Method (validated against tests/fixtures):
  1. Edge VOTE, not edge magnitude. A tile border is a line present at the same
     coordinate across many rows; artwork edges scatter. Counting rows that carry
     a strong gradient beats summing gradient magnitude, which lets bright artwork
     outvote a thin border.
  2. Pitch by autocorrelation of the vote signal, refined parabolically.
  3. Phase by folding the vote signal modulo the pitch. Tiles emit TWO impulse
     trains per period (leading and trailing borders), so the fold has two peaks.
  4. Disambiguate by arc length: the tile interior is the LONGER of the two arcs
     (e.g. 203px tile vs 52px gap). Its start is the leading border.
  5. Prune to the contiguous run of lines that actually carry border evidence --
     the raw lattice extends across the detail panel, which has no tiles.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = ["Axis", "Lattice", "fit_axis", "fit_lattice"]


@dataclass(frozen=True, slots=True)
class Axis:
    """A fitted 1-D lattice along one image axis."""

    pitch: float
    """Distance between consecutive tile origins, in pixels."""
    extent: int
    """Tile size along this axis (interior), in pixels."""
    origins: tuple[int, ...]
    """Absolute coordinates of each tile's leading border."""
    quality: float
    """Fold peak / median. Below ~2.5 the fit is not trustworthy."""

    @property
    def count(self) -> int:
        return len(self.origins)


@dataclass(frozen=True, slots=True)
class Lattice:
    """The fitted tile grid for a frame."""

    cols: Axis
    rows: Axis

    def box(self, row: int, col: int) -> tuple[int, int, int, int]:
        """(left, top, right, bottom) of one tile, in absolute frame coordinates."""
        x, y = self.cols.origins[col], self.rows.origins[row]
        return (x, y, x + self.cols.extent, y + self.rows.extent)

    @property
    def shape(self) -> tuple[int, int]:
        return (self.rows.count, self.cols.count)


def _edge_vote(roi: np.ndarray, axis: int, percentile: float = 92.0) -> np.ndarray:
    """Count lines carrying a strong gradient at each coordinate.

    Deliberately *not* a magnitude sum: see module docstring step 1.
    """
    d = np.abs(np.diff(roi, axis=axis))
    if axis == 1:
        thresh = np.percentile(d, percentile, axis=1, keepdims=True)
        return (d > thresh).sum(0).astype(float)
    thresh = np.percentile(d, percentile, axis=0, keepdims=True)
    return (d > thresh).sum(1).astype(float)


def _autocorr_pitch(signal: np.ndarray, lo: int, hi: int) -> float:
    centred = signal - signal.mean()
    ac = np.correlate(centred, centred, "full")[len(centred) - 1 :]
    hi = min(hi, len(ac) - 1)
    if hi <= lo + 1:
        raise ValueError(f"pitch search window too small: [{lo}, {hi})")
    k = int(np.argmax(ac[lo:hi])) + lo
    if 0 < k < len(ac) - 1:  # parabolic sub-pixel refinement
        y0, y1, y2 = ac[k - 1], ac[k], ac[k + 1]
        denom = y0 - 2 * y1 + y2
        if denom:
            return float(k + 0.5 * (y0 - y2) / denom)
    return float(k)


def _fold(signal: np.ndarray, pitch: float) -> np.ndarray:
    """Average the signal over every period, giving one period's profile."""
    period = int(round(pitch))
    acc = np.zeros(period)
    cnt = np.zeros(period)
    idx = (np.round(np.arange(len(signal)) % pitch).astype(int)) % period
    np.add.at(acc, idx, signal)
    np.add.at(cnt, idx, 1.0)
    return acc / np.maximum(cnt, 1.0)


def _two_clusters(profile: np.ndarray, tol_frac: float = 0.06) -> tuple[int, int]:
    """Top two peaks, suppressing bins adjacent to an already-chosen peak."""
    period = len(profile)
    tol = max(2, int(period * tol_frac))
    chosen: list[int] = []
    for raw in np.argsort(profile)[::-1]:
        i = int(raw)
        if all(min(abs(i - t), period - abs(i - t)) > tol for t in chosen):
            chosen.append(i)
            if len(chosen) == 2:
                break
    if len(chosen) < 2:
        raise ValueError("could not locate two distinct border families")
    return chosen[0], chosen[1]


def _prune(
    votes: np.ndarray, origins: list[int], offset: int, extent: int, keep_frac: float
) -> list[int]:
    """Keep the longest contiguous run of origins backed by real border evidence.

    Scored on the WEAKER of a candidate's leading and trailing border. A tile has
    both; the detail-panel edge is a strong lone border with no partner `extent`
    pixels later, so single-border scoring wrongly keeps it (observed: 7 columns
    found on a 6-column 3:2 frame).
    """
    if not origins:
        return []

    def border(x: int) -> float:
        i = x - offset
        lo, hi = max(0, i - 3), min(len(votes), i + 4)
        return float(votes[lo:hi].max()) if hi > lo else 0.0

    scores = [min(border(x), border(x + extent)) for x in origins]
    # Median, not max: a selected tile's bright gold border is an outlier that
    # inflates max() enough to prune genuine columns (observed on mat_top_selected).
    cutoff = keep_frac * float(np.median(scores))

    best: list[int] = []
    run: list[int] = []
    for x, s in zip(origins, scores, strict=True):
        if s >= cutoff:
            run.append(x)
        else:
            if len(run) > len(best):
                best = run
            run = []
    return run if len(run) > len(best) else best


def fit_axis(
    roi: np.ndarray,
    axis: int,
    offset: int,
    min_pitch: int,
    max_pitch: int,
    keep_frac: float = 0.30,
) -> Axis:
    """Fit the lattice along one axis of a greyscale ROI.

    `axis` is 1 for columns (vertical borders) and 0 for rows.
    `offset` is the ROI's origin in the full frame, added back into the result.
    """
    votes = _edge_vote(roi, axis)
    pitch = _autocorr_pitch(votes, min_pitch, max_pitch)
    profile = _fold(votes, pitch)
    period = len(profile)

    a, b = _two_clusters(profile)
    arc_ab, arc_ba = (b - a) % period, (a - b) % period
    start, extent = (a, arc_ab) if arc_ab > arc_ba else (b, arc_ba)

    span = roi.shape[1] if axis == 1 else roi.shape[0]
    n = max(int((span - start) // pitch) + 1, 0)
    origins = [int(round(offset + start + k * pitch)) for k in range(n)]
    origins = [x for x in origins if x + extent <= offset + span]
    origins = _prune(votes, origins, offset, int(extent), keep_frac)

    quality = float(profile.max() / max(np.median(profile), 1e-9))
    return Axis(pitch=pitch, extent=int(extent), origins=tuple(origins), quality=quality)


def fit_lattice(
    grey: np.ndarray,
    roi: tuple[float, float, float, float] = (0.06, 0.08, 0.74, 0.90),
    keep_frac: float = 0.30,
) -> Lattice:
    """Fit the tile grid of a greyscale frame.

    `roi` is fractional (left, top, right, bottom) -- a generous window around the
    grid, never a tile coordinate. Overshooting into the detail panel is fine;
    `_prune` removes lattice positions that carry no border evidence.
    """
    h, w = grey.shape
    x0, y0 = int(w * roi[0]), int(h * roi[1])
    x1, y1 = int(w * roi[2]), int(h * roi[3])
    sub = grey[y0:y1, x0:x1].astype(float)

    cols = fit_axis(sub, 1, x0, int(w * 0.04), int(w * 0.14), keep_frac)
    rows = fit_axis(sub, 0, y0, int(h * 0.12), int(h * 0.30), keep_frac)
    return Lattice(cols=cols, rows=rows)
