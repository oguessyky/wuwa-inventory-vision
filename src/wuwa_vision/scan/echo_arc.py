# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""The 声骸 page's slot arc: which echo sits where (D377).

Down the arc right of the figure stand five slots, the main one at the top: each the echo's
picture in a circle, its cost above it on the right, its +level under it, its set's badge on the
lower left. They stand where they stand, in the height's units from the right edge (D9: no pixel
constants): measured on seven frames of five resonators, the +level labels at y 0.315, 0.509,
0.638, 0.765 and 0.883 on every one.

- **Cost and level** are read slot by slot, a crop each, made larger: over the whole arc OCR
  missed half the small cost digits; this way it read all 35.
- **Which echo**, by its picture against the catalogue's (as the portraits' head icons, D344),
  among 计算's echoes of that cost -- the ones a resonator can wear (D373): sure at `SURE` or more
  and `LEAD` ahead of any other picture. A 异相 form is drawn in other colours than its plain
  echo, the only picture there is, and is unsure: it is named when clicked.
- **Which set**, by its badge against the sets' pictures.

Every region stops above 0.93 of the height; the UID, bottom right, is never read.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from ..ocr import character as ocr
from ..ocr.engine import read_line

#: A picture's match is sure at this or more, and this far ahead of any other picture.
SURE = 0.8
LEAD = 0.15
#: Below this, with no level under it, a slot holds nothing.
EMPTY = 0.5
#: A badge's match is sure at this or more, this far ahead of the next set.
SET_SURE = 0.55
SET_LEAD = 0.1
#: The pictures' backdrop, the arc's dark circle.
_BACKDROP = (20, 22, 28, 255)
#: The catalogue's picture, at this many of the slot's radii across, is the echo at its size; its
#: middle, `MIDDLE` radii each way, is matched within `REACH` radii of the slot's centre.
ACROSS = (1.8, 2.0, 2.2, 2.4)
MIDDLE = 0.55
REACH = 1.25
#: The badge: on the slot's lower left, `BADGE` of its radius; matched as the echo is.
BADGE = 0.22
BADGE_ACROSS = (2.0, 2.2, 2.4)
BADGE_MIDDLE = 0.7
BADGE_REACH = 1.8


@dataclass(frozen=True)
class Slot:
    """One slot, in the height's units from the right edge: its circle (x, y, radius), its cost
    digit and its +level label (x, y)."""

    centre: tuple[float, float, float]
    cost: tuple[float, float]
    level: tuple[float, float]


#: Measured on 爱弥斯's page (3437x1437) and checked on the other six frames.
SLOTS = (
    Slot((0.704, 0.268, 0.066), (0.656, 0.221), (0.674, 0.315)),
    Slot((0.645, 0.473, 0.047), (0.603, 0.430), (0.613, 0.509)),
    Slot((0.652, 0.602, 0.047), (0.611, 0.561), (0.622, 0.638)),
    Slot((0.692, 0.727, 0.047), (0.652, 0.687), (0.662, 0.765)),
    Slot((0.769, 0.846, 0.047), (0.730, 0.805), (0.740, 0.883)),
)
_COST = re.compile(r"^\D{0,2}([1-4])\D{0,2}$")


def _on_backdrop(path: Path) -> np.ndarray:
    from PIL import Image

    im = Image.open(path).convert("RGBA")
    back = Image.new("RGBA", im.size, _BACKDROP)
    return np.asarray(Image.alpha_composite(back, im).convert("RGB"))


class EchoArt:
    """The pictures a slot is named by: each echo's and each set's, and what 计算 knows of the
    echoes (their cost, their sets)."""

    def __init__(self, echoes: dict[str, np.ndarray], sets: dict[str, np.ndarray],
                 known: dict[str, dict] | None = None,
                 drawn_as: dict[str, str] | None = None) -> None:
        self.echoes = echoes
        self.sets = sets
        self.known = known or {}
        #: which picture each name is drawn with: one picture, one echo (a 共鸣回响· twin, a 异相
        #: form drawn as its plain echo)
        self.drawn_as = drawn_as or {n: n for n in echoes}
        self._sized: dict[tuple, list[tuple[str, np.ndarray]]] = {}

    @classmethod
    def from_catalogue(cls, directory: Path | None = None) -> EchoArt | None:
        """The catalogue's pictures, among the echoes 计算 knows (D373); None without them."""
        if directory is None:
            from ..catalogue import CATALOGUE_DIR

            directory = Path(CATALOGUE_DIR)
        try:
            index = json.loads((directory / "echoes.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        try:
            calc = json.loads((directory / "calc.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            calc = {}
        drawn: dict[str, str] = index.get("echoes") or {}
        known: dict[str, dict] = calc.get("echoes") or {}
        groups: dict[str, list[str]] = {}
        for name in list(known) or list(drawn):
            # a 异相 form has no picture of its own: its plain echo's
            file = drawn.get(name) or drawn.get(name.removeprefix("异相·"))
            if file and (directory / "echoes" / file).exists():
                groups.setdefault(file, []).append(name)
        pictures: dict[str, np.ndarray] = {}
        drawn_as: dict[str, str] = {}
        for file, names in groups.items():
            # one picture, one name: the one it is drawn for, not a form drawn with it
            own = [n for n in names if drawn.get(n) == file]
            first = own[0] if own else names[0]
            pictures[first] = _on_backdrop(directory / "echoes" / file)
            drawn_as.update({n: first for n in names})
        sets = {n: _on_backdrop(directory / "echoes" / f)
                for n, f in (index.get("sets") or {}).items()
                if (directory / "echoes" / f).exists()
                and (not calc.get("sets") or n in calc["sets"])}
        return cls(pictures, sets, known, drawn_as)

    def cost_of(self, name: str) -> int | None:
        cost = (self.known.get(name) or {}).get("cost")
        return int(cost) if cost else None

    def middles(self, kind: str, r: float, across: float, middle: float,
                names: tuple[str, ...]) -> list[tuple[str, np.ndarray]]:
        key = (kind, round(r), across, middle, names)
        if key not in self._sized:
            source = self.echoes if kind == "echo" else self.sets
            d = max(8, round(across * r))
            half = max(2, round(middle * r))
            out = []
            for name in names:
                a = cv2.resize(source[name], (d, d), interpolation=cv2.INTER_AREA)
                c = d // 2
                out.append((name, np.ascontiguousarray(a[c - half:c + half, c - half:c + half])))
            self._sized[key] = out
        return self._sized[key]


def _area(rgb: np.ndarray, cx: float, cy: float, reach: float) -> np.ndarray:
    h, w = rgb.shape[:2]
    return np.ascontiguousarray(rgb[max(0, int(cy - reach)):min(h, int(cy + reach)),
                                    max(0, int(cx - reach)):min(w, int(cx + reach))])


def _scores(area: np.ndarray, sized: list[tuple[str, np.ndarray]]) -> dict[str, float]:
    best: dict[str, float] = {}
    for name, middle in sized:
        if middle.shape[0] >= area.shape[0] or middle.shape[1] >= area.shape[1]:
            continue
        score = float(cv2.matchTemplate(area, middle, cv2.TM_CCOEFF_NORMED).max())
        best[name] = max(best.get(name, -1.0), score)
    return best


def _text(rgb: np.ndarray, x: float, y: float, half_w: float, half_h: float,
          scale: float) -> str:
    """The text in a small box (height units, x from the right edge), made larger first."""
    h, w = rgb.shape[:2]
    cx, cy = w - x * h, y * h
    crop = rgb[max(0, int(cy - half_h * h)):int(cy + half_h * h),
               max(0, int(cx - half_w * h)):int(cx + half_w * h)]
    if crop.size == 0:
        return ""
    crop = cv2.resize(np.ascontiguousarray(crop), None, fx=scale, fy=scale,
                      interpolation=cv2.INTER_CUBIC)
    # recognition only: where the text is, the slot says (0.7 s a crop with detection, D377)
    return read_line(crop)[0].strip()


def _level(text: str) -> int | None:
    found = ocr._PLUS.search(text)
    return int(found.group(1)) if found else None


def _cost(text: str) -> int | None:
    found = _COST.match(text.replace(" ", ""))
    return int(found.group(1)) if found else None


def read_slots(rgb: np.ndarray, art: EchoArt | None) -> list[dict]:
    """The five slots, the main one first: each `{"slot", "echo", "sure", "cost", "level",
    "set"}` -- `echo` None when its picture is unsure or there are no pictures -- or `{"slot",
    "empty": True}` when it holds nothing."""
    h, w = rgb.shape[:2]
    out = []
    for n, slot in enumerate(SLOTS, 1):
        x, y, rr = slot.centre
        cx, cy, r = w - x * h, y * h, rr * h
        level = _level(_text(rgb, *slot.level, 0.03, 0.015, 3))
        if level is None:
            # a wider crop takes in the arc's edge, a narrower one may clip "+": the other once
            level = _level(_text(rgb, *slot.level, 0.025, 0.018, 2))
        cost = _cost(_text(rgb, *slot.cost, 0.018, 0.02, 3))
        echo, sure, a_set, top = _which(rgb, cx, cy, r, cost, art)
        if level is None and cost is None and top < EMPTY:
            out.append({"slot": n, "empty": True})
            continue
        if echo is not None and cost is None:
            cost = art.cost_of(echo) if art is not None else None
        if a_set is None and art is not None:
            a_set = _set(rgb, cx, cy, r, art, echo)
        out.append({"slot": n, "echo": echo, "sure": sure, "cost": cost, "level": level,
                    "set": a_set})
    return out


def _which(rgb: np.ndarray, cx: float, cy: float, r: float, cost: int | None,
           art: EchoArt | None) -> tuple[str | None, bool, str | None, float]:
    """(the echo, whether sure, a set when known by it, the best score)."""
    if art is None or not art.echoes:
        return None, False, None, 0.0
    names = tuple(sorted(n for n in art.echoes
                         if cost is None or art.cost_of(n) in (None, cost)))
    if not names:
        return None, False, None, 0.0
    area = _area(rgb, cx, cy, REACH * r)
    best: dict[str, float] = {}
    for across in ACROSS:
        for name, score in _scores(area, art.middles("echo", r, across, MIDDLE, names)).items():
            best[name] = max(best.get(name, -1.0), score)
    if not best:
        return None, False, None, 0.0
    ranked = sorted(best.items(), key=lambda kv: -kv[1])
    top, score = ranked[0]
    # ahead of any other picture: a name drawn with the same one is no rival
    rival = next((s for n, s in ranked[1:]
                  if art.drawn_as.get(n, n) != art.drawn_as.get(top, top)), -1.0)
    sure = score >= SURE and score - rival >= LEAD
    if sure and cost is not None and art.cost_of(top) not in (None, cost):
        sure = False  # the slot shows another cost: not this echo
    return (top if sure else None), sure, None, score


def _set(rgb: np.ndarray, cx: float, cy: float, r: float, art: EchoArt,
         echo: str | None) -> str | None:
    """The set by the slot's badge; among the echo's own sets when it is named."""
    if not art.sets:
        return None
    own = (art.known.get(echo or "") or {}).get("sets") or []
    names = tuple(sorted(n for n in art.sets if not own or n in own)) or tuple(sorted(art.sets))
    br = BADGE * r
    bx, by = cx - 0.707 * r, cy + 0.707 * r
    area = _area(rgb, bx, by, BADGE_REACH * br)
    best: dict[str, float] = {}
    for across in BADGE_ACROSS:
        for name, score in _scores(area, art.middles("set", br, across, BADGE_MIDDLE,
                                                     names)).items():
            best[name] = max(best.get(name, -1.0), score)
    if not best:
        return None
    ranked = sorted(best.items(), key=lambda kv: -kv[1])
    top, score = ranked[0]
    rival = ranked[1][1] if len(ranked) > 1 else -1.0
    return top if score >= SET_SURE and score - rival >= SET_LEAD else None
