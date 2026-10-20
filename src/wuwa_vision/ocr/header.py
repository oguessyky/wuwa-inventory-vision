# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Header parsing: the tab label and the game's own item count.

The header reads e.g. `资源 111/1000` or `素材 153/1000`. The left number is the
number of UNIQUE entries the tab holds, straight from the game -- a free oracle
for scan completeness (PLAN.md D8). A scan is provably complete when the number
of distinct icon hashes equals it.

Tab identity must come from here, never from the left rail icons: co-op friend
avatars overlay the rail (observed on several captures).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

from .engine import read_text

_COUNT = re.compile(r"(\d{1,5})\s*/\s*(\d{2,6})")
#: Header occupies the top-left strip, left of the currency counters.
HEADER_BOX = (0.0, 0.0, 0.30, 0.075)
#: Taller retry. On 3:2 the header sits at ~0.09 of the height, below HEADER_BOX,
#: so it read nothing there. The taller box is NOT the default: on 21:9 it cut
#: 资源 to 资 (D28). Used only when the default box finds no count.
HEADER_BOX_TALL = (0.0, 0.0, 0.30, 0.12)


@dataclass(frozen=True, slots=True)
class Header:
    label: str | None
    """Tab name, e.g. 资源 or 素材."""
    unique_items: int | None
    """Entries currently held -- the completeness oracle."""
    capacity: int | None
    confidence: float


def crop_header(
    rgb: np.ndarray, box: tuple[float, float, float, float] = HEADER_BOX
) -> np.ndarray:
    h, w = rgb.shape[:2]
    left, top, right, bottom = box
    return rgb[int(h * top) : int(h * bottom), int(w * left) : int(w * right)]


def parse(rgb: np.ndarray) -> Header:
    head = _parse(rgb, HEADER_BOX)
    if head.unique_items is None:
        tall = _parse(rgb, HEADER_BOX_TALL)
        if tall.unique_items is not None:
            return tall
    return head


def _parse(rgb: np.ndarray, box: tuple[float, float, float, float]) -> Header:
    lines = read_text(crop_header(rgb, box))
    label: str | None = None
    unique = capacity = None
    conf = 0.0
    for text, c in lines:
        m = _COUNT.search(text.replace(" ", ""))
        if m:
            unique, capacity = int(m.group(1)), int(m.group(2))
            conf = max(conf, c)
            stripped = _COUNT.sub("", text).strip()
            if stripped and label is None:
                label = stripped
        elif label is None and any("一" <= ch <= "鿿" for ch in text):
            label = text.strip()
            conf = max(conf, c)
    return Header(
        label=canonical_label(label), unique_items=unique, capacity=capacity, confidence=conf
    )


#: Bag tab names seen in the game. The header OCR misreads them now and then --
#: 武器 came back as 器润 live, 资源 as 资 with a taller crop -- and the label is
#: what tabs are keyed and skipped by (D35).
KNOWN_TABS: tuple[str, ...] = ("武器", "声骸", "补给", "资源", "素材", "任务", "特殊")


def canonical_label(raw: str | None) -> str | None:
    """Snap an OCR'd tab label to the one known tab it shares a character with.

    Only an unambiguous overlap snaps; anything else is returned as read, so a new
    or unrecognised tab still gets its own scan instead of joining a wrong one.
    """
    if raw is None:
        return None
    raw = raw.strip()
    if raw in KNOWN_TABS:
        return raw
    hits = [tab for tab in KNOWN_TABS if set(tab) & set(raw)]
    return hits[0] if len(hits) == 1 else raw
