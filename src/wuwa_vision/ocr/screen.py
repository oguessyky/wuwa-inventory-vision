# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Which screen a frame is (D331): the bag, and which tab, or a resonator's own, and which one.

Both are named by the title at the top left. The bag's says its count (`资源 111/1000`,
`武器 175/2000`); a resonator's screen says only its name (`属性详情`, `技能`, `武器`,
`共鸣链`), and the echo bag opened from a resonator says COST and 全部. So one OCR of that strip
says which kind of screen this is and, for the bag, the tab and the game's count (the
completeness check, D8).

`ScreenMemo` reads a strip once: it keeps each title it has read with the box its text was found
in, and a frame whose pixels in one of those boxes match is that screen again -- scrolling a tab,
clicking an item, coming back to a tab or a screen seen before. The box is the title's own text
(its icon, and room to its right for a count), not a fixed band: a tile row scrolled up reaches
into any band tall enough for the 3:2 header (16:10: tiles at 0.105 of the height, 3:2: the
header down to 0.10).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from . import engine
from .header import _COUNT, KNOWN_TABS, Header, canonical_label

#: The strip read, in units of the window's height from its top-left corner (D9): the header
#: ends near 0.3 on every capture and its text by 0.101 (3:2); the currency is right of 0.8.
STRIP = (0.6, 0.12)
#: Room kept left of the title's text for its icon, and right of it for a count, in the
#: height's units: the bag's 武器 and a resonator's 武器 look alike until the count.
ICON = 0.07
ROOM = 0.25
#: Largest per-cell change (0-255, 64x16 thumbnail) that is still the same title. The header
#: memo's measure (D29): a tab switch moved the max by 143; views of one tab, by at most 8.
SAME = 20.0
#: Titles kept: the bag's seven tabs and a resonator's six screens, with room.
KEEP = 24

_EMPTY = Header(label=None, unique_items=None, capacity=None, confidence=0.0)
_DIGIT = set("0123456789")


@dataclass(frozen=True, slots=True)
class Screen:
    kind: str
    """"bag", "resonator", or "unknown" (no title read: a loading screen, a menu)."""
    tab: str | None = None
    """The bag's tab (资源, 武器 ...), snapped onto the known tabs (D35)."""
    screen: str | None = None
    """A resonator's screen: attributes, skills, weapon, echo, echoes, chain (D270)."""
    header: Header = _EMPTY
    """The bag's header: label and count. Empty for anything else."""
    box: tuple[float, float, float, float] | None = field(default=None, compare=False)
    """Where the title was found, in the height's units: what the memo compares."""


def strip(rgb: np.ndarray) -> np.ndarray:
    h, w = rgb.shape[:2]
    return np.ascontiguousarray(rgb[: int(h * STRIP[1]), : min(w, int(h * STRIP[0]))])


def engine_call(crop: np.ndarray) -> list[tuple[tuple[float, float, float, float], str, float]]:
    """One OCR: each line's box in the crop's pixels, its text and confidence."""
    if crop.size == 0:
        return []
    result, _ = engine._engine()(crop)
    out = []
    for points, text, conf in result or []:
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        out.append(((min(xs), min(ys), max(xs), max(ys)), str(text).strip(), float(conf)))
    return out


def read_title(rgb: np.ndarray) -> list[tuple[tuple[float, float, float, float], str, float]]:
    """The strip's lines, boxes in units of the frame's height."""
    h = rgb.shape[0]
    return [((x0 / h, y0 / h, x1 / h, y1 / h), text, conf)
            for (x0, y0, x1, y1), text, conf in engine_call(strip(rgb))]


def _cjk(text: str) -> bool:
    return any("一" <= ch <= "鿿" for ch in text)


def judge(lines: list[tuple[tuple[float, float, float, float], str, float]]) -> Screen:
    """What the strip's lines say this screen is."""
    words = " ".join(text for _, text, _ in lines)

    def box(chosen: list) -> tuple[float, float, float, float] | None:
        if not chosen:
            return None
        x0 = min(b[0] for b, _, _ in chosen)
        y0 = min(b[1] for b, _, _ in chosen)
        x1 = max(b[2] for b, _, _ in chosen)
        y1 = max(b[3] for b, _, _ in chosen)
        return (max(0.0, x0 - ICON), max(0.0, y0 - 0.005), x1 + ROOM, y1 + 0.005)

    if "COST" in words.upper() or "全部" in words:  # the echo bag opened from a resonator
        return Screen("resonator", screen="echo", box=box(lines))
    # the bag: a label and its count, as header.parse reads them
    label = label_line = count_line = None
    unique = capacity = None
    conf = 0.0
    for line in lines:
        _, text, c = line
        found = _COUNT.search(text.replace(" ", ""))
        if found and unique is None:
            unique, capacity = int(found.group(1)), int(found.group(2))
            conf, count_line = max(conf, c), line
            rest = _COUNT.sub("", text).strip()
            if rest and label is None and _cjk(rest):
                label, label_line = rest, line
        elif label is None and _cjk(text):
            label, label_line, conf = text.strip(), line, max(conf, c)
    title = [line for line in (label_line, count_line) if line is not None]
    if unique is not None:
        head = Header(label=canonical_label(label), unique_items=unique, capacity=capacity,
                      confidence=conf)
        return Screen("bag", tab=head.label, header=head, box=box(title))
    if label is None:
        return Screen("unknown")
    # a title with no count: a resonator's screen, unless a count was there and misread
    for word, kind in (("属性", "attributes"), ("鸣链", "chain"), ("技能", "skills"),
                       ("声骸", "echoes"), ("器", "weapon")):
        if word in label:
            if kind == "weapon" and any(set(text) & _DIGIT for _, text, _ in lines):
                break  # 武器 with numbers beside it: the bag's, its count not made out
            return Screen("resonator", screen=kind, box=box(title))
    snapped = canonical_label(label)
    if snapped == "声骸":
        # the bag's 声骸 tab says its count (声骸 1402/3000); a 声骸 title with none is a
        # resonator's 声骸 page, read a little wrong (声骼, 骸): taken for the bag's, it was
        # skipped (D340). The bag's, its count unread, is skipped either way: nothing is lost.
        return Screen("resonator", screen="echoes", box=box(title))
    if snapped in KNOWN_TABS:  # the bag, its count unread: the tab is still known (D28)
        head = Header(label=snapped, unique_items=None, capacity=None, confidence=conf)
        return Screen("bag", tab=snapped, header=head, box=box(title))
    return Screen("unknown")


def classify(rgb: np.ndarray) -> Screen:
    return judge(read_title(rgb))


def _thumb(rgb: np.ndarray, box: tuple[float, float, float, float]) -> np.ndarray | None:
    h, w = rgb.shape[:2]
    x0, y0, x1, y1 = (int(v * h) for v in box)
    crop = rgb[max(0, y0) : min(h, y1), max(0, x0) : min(w, x1)]
    if crop.size == 0:
        return None
    return cv2.resize(crop, (64, 16), interpolation=cv2.INTER_AREA).astype(np.float32)


@dataclass
class ScreenMemo:
    """Reads a title strip only when it is one not seen before (D331, after D29's header memo)."""

    known: list[tuple[tuple[float, float, float, float], np.ndarray, Screen]] = field(
        default_factory=list)
    last: Screen | None = None
    reads: int = 0

    def look(self, rgb: np.ndarray) -> Screen:
        for n, (box, thumb, screen) in enumerate(self.known):
            now = _thumb(rgb, box)
            if now is not None and now.shape == thumb.shape and \
                    float(np.abs(now - thumb).max()) < SAME:
                if n:
                    self.known.insert(0, self.known.pop(n))
                self.last = screen
                return screen
        screen = classify(rgb)
        self.reads += 1
        # nothing read is not remembered: a title misread once is read again next time. Nor is
        # a bag title that is none of the game's tabs: 素材 once read as 国, and every view of
        # the tab was 国 until it was left.
        misread = screen.kind == "bag" and screen.tab not in KNOWN_TABS
        thumb = _thumb(rgb, screen.box) if screen.box is not None and not misread else None
        if thumb is not None:
            self.known.insert(0, (screen.box, thumb, screen))
            del self.known[KEEP:]
        self.last = screen
        return screen

