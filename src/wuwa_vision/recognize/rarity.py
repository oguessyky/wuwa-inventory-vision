# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Rarity classification from the tile's colour bar.

Measured across all 29 original captures (PLAN.md D7). Green/blue/purple are
exact to +/-1; gold carries an animated sheen, so matching is nearest-centroid
rather than equality.

Critically, rarity is an ATTRIBUTE sampled inside an already-located tile -- never
a locator. 1-star items (flowers, ingredients) render with NO bar at all, which is
why the colour-band approach to finding rows was abandoned.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Rarity -> representative bar colours. Gold has multiple observed samples.
PALETTE: dict[int, tuple[tuple[int, int, int], ...]] = {
    2: ((123, 207, 125),),
    3: ((81, 152, 255), (81, 153, 255)),
    4: ((200, 92, 255), (200, 91, 254), (201, 93, 255)),
    5: ((247, 235, 166), (252, 247, 175), (254, 236, 172), (247, 239, 166)),
}

#: Below this saturation the tile has no bar at all -> 1-star.
MIN_SATURATION = 45
#: Max RGB distance to accept a palette match.
MAX_DISTANCE = 60.0
#: A real bar is a flat band spanning the tile width. Measured coverage for true
#: bars is >0.85; isolated artwork bleeding into the strip sits far below this.
MIN_BAR_COVERAGE = 0.60


@dataclass(frozen=True, slots=True)
class RarityRead:
    rarity: int
    """2-5 from the bar; 1 when no bar is present."""
    confidence: float
    """1.0 = exact palette hit. Lower means further from any centroid."""
    sampled: tuple[int, int, int]


def classify(bar_pixels: np.ndarray) -> RarityRead:
    """Classify the rarity bar from a strip of pixels sampled inside a tile.

    `bar_pixels` is (N, 3) uint8. Absence of a saturated colour is a valid answer
    (1-star), not a failure.
    """
    if bar_pixels.size == 0:
        return RarityRead(1, 0.0, (0, 0, 0))

    px = bar_pixels.reshape(-1, 3).astype(int)
    sat = px.max(axis=1) - px.min(axis=1)
    strong = px[sat > MIN_SATURATION]
    coverage = float(strong.shape[0]) / float(px.shape[0])

    # No bar at all -> 1-star. This is the flower/ingredient case and is a valid
    # answer, not a failure. Partial coverage means artwork bleeding into the
    # strip, not a bar: a bar spans the full tile width.
    if coverage < MIN_BAR_COVERAGE:
        med = tuple(int(v) for v in np.median(px, axis=0))
        return RarityRead(1, 1.0 - coverage, med)  # type: ignore[arg-type]

    # Sample the bar CORE. The bar fades at its edges and is alpha-blended over a
    # dark background, so a plain median lands around 0.54x the true colour
    # (observed: (108,68,137) for a (200,92,255) purple bar). Taking the most
    # saturated decile recovers the actual palette colour.
    strong_sat = strong.max(axis=1) - strong.min(axis=1)
    core = strong[strong_sat >= np.percentile(strong_sat, 90)]
    sample = np.median(core if core.size else strong, axis=0)
    best_rarity, best_dist = 1, float("inf")
    for rarity, colours in PALETTE.items():
        for c in colours:
            dist = float(np.linalg.norm(sample - np.array(c)))
            if dist < best_dist:
                best_rarity, best_dist = rarity, dist

    if best_dist > MAX_DISTANCE:
        # Full-width saturated band that matches no known palette entry. Genuinely
        # unknown -- flagged (0), never guessed. Fail open on data (D15).
        return RarityRead(0, 0.0, tuple(int(v) for v in sample))  # type: ignore[arg-type]
    confidence = max(0.0, 1.0 - best_dist / MAX_DISTANCE)
    return RarityRead(best_rarity, confidence, tuple(int(v) for v in sample))  # type: ignore[arg-type]
