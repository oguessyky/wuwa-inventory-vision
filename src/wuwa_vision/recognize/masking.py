# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Badge masking for icon crops.

Tiles overlay status badges on the artwork. They are nuisance variables: the same
item is the same item whether or not it is new or craftable, so a badge must not
move its embedding.

Ported and extended from the sibling `wucv` project, which masks the `新` badge
during SSIM re-ranking (`valid_mask[:h*0.235, w*0.781:] = False`). Two changes:

1. **Mask before embedding, not only at re-rank.** Masking at comparison time
   still lets the badge pollute the embedding itself. Masking the crop first makes
   the embedding badge-invariant, provided it is applied to gallery and query
   alike -- which is why this lives on the crop path, not the compare path.
2. **Also mask the bottom-right `+` badge.** Measured at x >= 0.78, y >= 0.86 of
   the icon crop (visible on mat_flowers_nobar r0c6/r0c7). wucv's mask covers only
   the top-right corner and would leave this one in.

Masked regions are filled with the crop's median colour rather than a constant, so
no artificial high-contrast edge is introduced for the encoder to latch onto.
"""

from __future__ import annotations

import numpy as np

#: (left, top, right, bottom) as fractions of the icon crop.
BADGE_REGIONS: tuple[tuple[float, float, float, float], ...] = (
    (0.780, 0.000, 1.000, 0.235),  # 新  - "new item", gold, top-right
    (0.780, 0.860, 1.000, 1.000),  # +   - obtainable/craftable, green, bottom-right
)


def apply_badge_mask(
    icon: np.ndarray,
    regions: tuple[tuple[float, float, float, float], ...] = BADGE_REGIONS,
) -> np.ndarray:
    """Return a copy of `icon` with badge corners flattened to the median colour."""
    if icon.size == 0:
        return icon
    out = icon.copy()
    h, w = out.shape[:2]
    fill = np.median(out.reshape(-1, out.shape[2]), axis=0).astype(out.dtype)
    for left, top, right, bottom in regions:
        x0, x1 = int(w * left), int(round(w * right))
        y0, y1 = int(h * top), int(round(h * bottom))
        if x1 > x0 and y1 > y0:
            out[y0:y1, x0:x1] = fill
    return out
