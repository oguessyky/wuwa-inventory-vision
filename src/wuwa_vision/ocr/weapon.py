# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""The 武器 tab's footer: "Lv. 90" (D61).

A weapon tile spends its footer on the level, not on a count, so the number the
bag reader takes from there is the level -- 122 weapons were stored as "owned 90"
before this. Reading it properly gives the level for free, which is what says
whether a weapon is finished.
"""

from __future__ import annotations

import re

import numpy as np

from .engine import _upscale, read_line

#: "Lv. 90", "Lv.90", "LV.90", "Lv 90" -- RapidOCR returns all four on the
#: fixtures, and a stray bracket sometimes rides along ("Lv. 90]").
_LEVEL = re.compile(r"[lL][vV]\s*[.,·]?\s*(\d{1,2})")
#: Weapons cap at 90; a bigger number is not a level.
MAX_LEVEL = 90


def read_level(crop: np.ndarray | None) -> tuple[int | None, float]:
    """Read a weapon tile's level. Returns (level, confidence).

    None means "this is not a weapon tile": the 武器 tab also holds the weapon EXP
    materials, which are ordinary bag tiles with a count in the footer.
    """
    if crop is None or crop.size == 0:
        return (None, 0.0)
    text, conf = read_line(_upscale(crop))
    match = _LEVEL.search(text)
    if not match:
        return (None, 0.0)
    level = int(match.group(1))
    return (level, conf) if 1 <= level <= MAX_LEVEL else (None, 0.0)
