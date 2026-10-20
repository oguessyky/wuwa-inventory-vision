# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""The currency counters at the top of the bag: 贝币 (shells) and 星声 (astrite).

Both sit in the top band, right of the tab header, as two pills: the 贝币 count
first, then 星声 with a "+" after it. Read left to right, the first number is
贝币 and the next is 星声 -- the same on 21:9 (6679896, 4395) and 3:2 (20205658,
36) in the fixture set. The band is the header's own strip (HEADER_BOX_TALL), so
no new geometry: its right half only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

from .engine import read_boxes
from .header import HEADER_BOX_TALL, crop_header

#: Right half of the header strip, where the currency pills are.
CURRENCY_BOX = (0.5, HEADER_BOX_TALL[1], 1.0, HEADER_BOX_TALL[3])
_NUMBER = re.compile(r"^\d{1,12}$")


@dataclass(frozen=True, slots=True)
class Currency:
    shells: int | None
    """贝币."""
    astrite: int | None
    """星声."""
    confidence: float


def parse(rgb: np.ndarray) -> Currency:
    numbers = []
    for x, text, conf in sorted(read_boxes(crop_header(rgb, CURRENCY_BOX))):
        digits = text.replace(",", "").replace(" ", "")
        if _NUMBER.match(digits):
            numbers.append((x, int(digits), conf))
    if not numbers:
        return Currency(None, None, 0.0)
    shells = numbers[0]
    astrite = numbers[1] if len(numbers) > 1 else None
    return Currency(
        shells=shells[1],
        astrite=astrite[1] if astrite else None,
        confidence=min(c for _, _, c in numbers[:2]),
    )
