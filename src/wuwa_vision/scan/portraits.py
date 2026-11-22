# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Whose screen it is, by the portraits on the right (D341).

A resonator's 技能, 武器, 声骸 and 共鸣链 screens do not say whose they are, and the portraits down
the right edge switch between resonators without passing 属性详情. The one selected wears rings and
a thin straight line at 30-50 degrees through it; the others only a thin arc of their rarity. On the
20 labelled captures the line and the rings together picked the right portrait 19 times, and the
one wrong had a margin of 1.09: every pick at `SURE` or more was right.

Who that portrait is, the catalogue's head icons cannot say well enough (the right name first in
14 of 23, by 0.01-0.03). So each resonator's portrait is learned where their name is read, on
属性详情, and known again on the other screens: the same artwork at the same size, compared as a
small thumbnail. Learned portraits are kept (`app_setting`), so a resonator is learned once.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from ..store.db import Store

#: Where the portraits are looked for, in the height's units from the right edge, and its top and
#: bottom; a portrait's centre is below `LOWEST` (the grid button under them is not one).
COLUMN = (0.16, 0.05, 0.88)
LOWEST = 0.84
#: The strip the line and the rings are measured in: wider, for the line runs out past the rings.
STRIP = 0.2
#: A portrait's radius, as a share of the height (0.034 on 3437x1437).
RADIUS = 0.034
#: How far ahead of the next the selected portrait must score to be trusted.
SURE = 1.3
#: A portrait's true radius, as a share of the height. The circles found wander (46-56 px on
#: 1437) and their centres by up to 15 px, which broke a fixed crop (the same portrait scored
#: -0.1 to 0.8); a picture of the fixed size, matched over a wider area, does not: the same
#: portrait 0.929 at least on the 20 captures, a different one 0.647 at most.
TRUE_RADIUS = 0.0362
#: The same portrait, by `_match`.
SAME = 0.8
#: The learned picture: 0.7 of the radius each way, at this many pixels across.
SIZE = 32
#: Kept in `app_setting` under this key: {name: the picture, base64 of its bytes}.
KEY = "resonator_portraits"


@dataclass(frozen=True)
class Selected:
    slot: int                    # 1 at the top
    x: float
    y: float
    r: float
    margin: float

    @property
    def sure(self) -> bool:
        return self.margin >= SURE


def circles(rgb: np.ndarray) -> list[tuple[float, float, float]]:
    """The portraits down the right edge, top to bottom: centre and radius, on one line."""
    h, w = rgb.shape[:2]
    x0, y0, y1 = int(w - COLUMN[0] * h), int(COLUMN[1] * h), int(COLUMN[2] * h)
    grey = cv2.medianBlur(cv2.cvtColor(np.ascontiguousarray(rgb[y0:y1, x0:w]),
                                       cv2.COLOR_RGB2GRAY), 5)
    r = RADIUS * h
    found = cv2.HoughCircles(grey, cv2.HOUGH_GRADIENT, dp=1.2, minDist=int(1.8 * r), param1=90,
                             param2=28, minRadius=int(0.8 * r), maxRadius=int(1.25 * r))
    if found is None:
        return []
    raw = [(float(x) + x0, float(y) + y0, float(rr)) for x, y, rr in found[0]]
    # the column is one line of one size: a ring or a button off it is not a portrait
    xm = float(np.median([c[0] for c in raw]))
    rm = float(np.median([c[2] for c in raw]))
    return sorted(((xm, y, rm) for x, y, _ in raw if abs(x - xm) < 0.4 * rm and y < LOWEST * h),
                  key=lambda c: c[1])


def _line(lab: np.ndarray, x: float, y: float, r: float, angle: float) -> float:
    """How strongly a thin straight line runs through (x, y) at `angle`, outside the portrait:
    its colour against the same distances a few degrees off it."""
    h, w = lab.shape[:2]

    def at(a: float, t: float) -> np.ndarray | None:
        rad = np.deg2rad(a)
        px, py = int(x + t * np.cos(rad)), int(y - t * np.sin(rad))
        return lab[py, px] if 0 <= px < w and 0 <= py < h else None

    score = []
    for base in (angle, angle + 180):
        for t in np.linspace(1.6 * r, 2.5 * r, 24):
            on = at(base, t)
            offs = [o for d in (-10, -6, 6, 10) if (o := at(base + d, t)) is not None]
            if on is not None and offs:
                score.append(float(np.linalg.norm(on - np.median(offs, axis=0))))
    return float(np.mean(score)) if score else 0.0


def _rings(lab: np.ndarray, x: float, y: float, r: float) -> float:
    """How unlike its surroundings the band around a portrait is."""
    h, w = lab.shape[:2]
    yy, xx = np.ogrid[:h, :w]
    d = np.sqrt((xx - x) ** 2 + (yy - y) ** 2)
    band = (d > 1.15 * r) & (d < 1.5 * r)
    out = (d > 1.75 * r) & (d < 2.1 * r) & (np.abs(yy - y) < 0.9 * r)
    if not band.any() or not out.any():
        return 0.0
    ref = np.median(lab[out], axis=0)
    return float(np.mean(np.linalg.norm(lab[band] - ref, axis=1) > 25))


def _scores(rgb: np.ndarray, found: list[tuple[float, float, float]]) -> np.ndarray:
    """How much each portrait looks selected: its line and its rings, each against the column's
    median."""
    h, w = rgb.shape[:2]
    # only the column's strip is looked at, for speed
    x0 = int(w - STRIP * h)
    lab = cv2.cvtColor(np.ascontiguousarray(rgb[:, x0:]), cv2.COLOR_RGB2LAB).astype(np.float32)
    local = [(x - x0, y, r) for x, y, r in found]
    lines = np.array([max(_line(lab, *c, a) for a in range(30, 52, 3)) for c in local])
    rings = np.array([_rings(lab, *c) for c in local])
    return lines / max(float(np.median(lines)), 1e-6) + rings / max(float(np.median(rings)), 1e-6)


def _pick(both: np.ndarray, found: list[tuple[float, float, float]]) -> Selected:
    order = np.argsort(-both)
    best = int(order[0])
    margin = float(both[best] / max(float(both[order[1]]), 1e-6))
    x, y, r = found[best]
    return Selected(slot=best + 1, x=x, y=y, r=r, margin=margin)


def selected(rgb: np.ndarray) -> Selected | None:
    """The selected portrait, or None when there is no column of portraits."""
    found = circles(rgb)
    if len(found) < 3:
        return None
    return _pick(_scores(rgb, found), found)


@dataclass(frozen=True)
class Column:
    """The column as one screen showed it (D370): each portrait's picture (`SIZE`, as learned)
    and the area round it to find another's in, and how much each looks selected."""

    pictures: tuple[np.ndarray, ...]
    areas: tuple[np.ndarray, ...]
    scores: tuple[float, ...]
    selected: Selected


def column(rgb: np.ndarray) -> Column | None:
    """The column of portraits on this screen, or None when there is none."""
    found = circles(rgb)
    if len(found) < 3:
        return None
    both = _scores(rgb, found)
    at = [Selected(slot=i + 1, x=x, y=y, r=r, margin=0.0) for i, (x, y, r) in enumerate(found)]
    return Column(pictures=tuple(picture(rgb, a) for a in at),
                  areas=tuple(_scaled(rgb, a, 1.3) for a in at),
                  scores=tuple(float(s) for s in both), selected=_pick(both, found))


def same_pick(a: list[float] | tuple[float, ...], b: list[float] | tuple[float, ...]) -> bool:
    """Whether two screens' selection scores say the same portrait is selected (D370). A sure
    pick (`SURE` ahead of the next) decides: both sure, the same one; one sure, its portrait is
    among the other's best (within `SURE` of its first); neither, the same one first."""
    if len(a) != len(b) or len(a) < 2:
        return False

    def first(s: list[float] | tuple[float, ...]) -> tuple[int, bool]:
        order = sorted(range(len(s)), key=lambda i: -s[i])
        return order[0], s[order[0]] >= SURE * max(s[order[1]], 1e-6)

    (fa, sa), (fb, sb) = first(a), first(b)
    if sa and sb:
        return fa == fb
    if sa or sb:
        sure, other = (fa, b) if sa else (fb, a)
        return other[sure] * SURE >= max(other)
    return fa == fb


def same_people(a: Column, b: Column) -> bool:
    """The same portraits in the same places: the column was not scrolled or changed."""
    if len(a.pictures) != len(b.pictures):
        return False
    for learned, area in zip(a.pictures, b.areas, strict=True):
        if area.shape[0] < SIZE or area.shape[1] < SIZE:
            return False
        if float(cv2.matchTemplate(area, learned, cv2.TM_CCOEFF_NORMED).max()) < SAME:
            return False
    return True


def same_selection(a: Column, b: Column) -> bool:
    """The user picked no other portrait between these two screens (D370): the same portraits,
    the same one selected."""
    return same_people(a, b) and same_pick(a.scores, b.scores)


#: The 漂泊者 is one portrait whatever their element (D370): learned and known as this.
ROVER = "漂泊者"


def plain(name: str) -> str:
    """A name as a portrait knows it: any 漂泊者 (a form, a head icon's 女漂泊者) is the 漂泊者."""
    return ROVER if ROVER in name else name


def _scaled(rgb: np.ndarray, at: Selected, reach: float) -> np.ndarray:
    """The square `reach` radii each way around the portrait, at the learned picture's scale."""
    h = rgb.shape[0]
    r = TRUE_RADIUS * h
    f = (SIZE / 2) / (0.7 * r)
    rr = reach * r
    crop = rgb[max(0, int(at.y - rr)):int(at.y + rr), max(0, int(at.x - rr)):int(at.x + rr)]
    return cv2.resize(np.ascontiguousarray(crop),
                      (max(1, round(crop.shape[1] * f)), max(1, round(crop.shape[0] * f))),
                      interpolation=cv2.INTER_AREA)


def picture(rgb: np.ndarray, at: Selected) -> np.ndarray:
    """The portrait to learn: inside its rings, SIZE pixels across."""
    return cv2.resize(_scaled(rgb, at, 0.7), (SIZE, SIZE), interpolation=cv2.INTER_AREA)


def _match(learned: np.ndarray, rgb: np.ndarray, at: Selected) -> float:
    area = _scaled(rgb, at, 1.3)
    if area.shape[0] < SIZE or area.shape[1] < SIZE:
        return 0.0
    return float(cv2.matchTemplate(area, learned, cv2.TM_CCOEFF_NORMED).max())


#: The catalogue's head icon is the portrait's own artwork (D344): its image, at this many of
#: the portrait's radii across, is the portrait at its size; its middle, this many radii each
#: way, is matched. Measured on 25 screens: the right icon 0.82-0.92, the next at most 0.63.
ICON_ACROSS = (2.6, 2.8, 3.0)
ICON_MIDDLE = 0.8
#: An icon's match is trusted at this or more, and this far ahead of the next.
ICON_SAME = 0.75
ICON_LEAD = 0.15
#: The icons' backdrop, as the column's.
_BACKDROP = (20, 22, 28, 255)


def icons_from(catalogue_dir: Path) -> dict[str, np.ndarray]:
    """The catalogue's head icons (D133, `avatars.json`) on the column's backdrop, by name; none
    without the catalogue."""
    from PIL import Image

    index = catalogue_dir / "avatars.json"
    if not index.exists():
        return {}
    out: dict[str, np.ndarray] = {}
    for name, file in json.loads(index.read_text(encoding="utf-8")).get("resonators", {}).items():
        path = catalogue_dir / "avatars" / file
        if path.exists():
            im = Image.open(path).convert("RGBA")
            back = Image.new("RGBA", im.size, _BACKDROP)
            out[name] = np.asarray(Image.alpha_composite(back, im).convert("RGB"))
    return out


class Portraits:
    """Whose portrait is selected: by the catalogue's head icons (D344), else by the portraits
    learned on 属性详情 (D341)."""

    def __init__(self, store: Store, icons: dict[str, np.ndarray] | None = None) -> None:
        self.store = store
        kept = json.loads(store.setting(KEY) or "{}")
        self.known: dict[str, np.ndarray] = {
            n: np.frombuffer(base64.b64decode(v), dtype=np.uint8).reshape(SIZE, SIZE, 3)
            for n, v in kept.items()}
        if icons is None:
            from ..catalogue import CATALOGUE_DIR

            icons = icons_from(Path(CATALOGUE_DIR))
        self.icons = icons
        self._sized: dict[tuple[int, float], list[tuple[str, np.ndarray]]] = {}

    def _icon_middles(self, r: float, across: float) -> list[tuple[str, np.ndarray]]:
        """Each icon's middle at a portrait of radius `r`, kept per size."""
        key = (round(r), across)
        if key not in self._sized:
            d = max(8, round(across * r))
            half = round(ICON_MIDDLE * r)
            sized = []
            for name, icon in self.icons.items():
                a = cv2.resize(icon, (d, d), interpolation=cv2.INTER_AREA)
                c = d // 2
                sized.append((name, np.ascontiguousarray(a[c - half:c + half, c - half:c + half])))
            self._sized[key] = sized
        return self._sized[key]

    def by_icon(self, rgb: np.ndarray, at: Selected) -> str | None:
        """Whose head icon the selected portrait is, when one is clearly it."""
        if not self.icons:
            return None
        r = TRUE_RADIUS * rgb.shape[0]
        reach = 1.4 * r
        area = np.ascontiguousarray(
            rgb[max(0, int(at.y - reach)):int(at.y + reach),
                max(0, int(at.x - reach)):int(at.x + reach)])
        best: dict[str, float] = {}
        for across in ICON_ACROSS:
            for name, middle in self._icon_middles(r, across):
                if middle.shape[0] >= area.shape[0] or middle.shape[1] >= area.shape[1]:
                    continue
                score = float(cv2.matchTemplate(area, middle, cv2.TM_CCOEFF_NORMED).max())
                best[name] = max(best.get(name, -1.0), score)
        if not best:
            return None
        ranked = sorted(best.items(), key=lambda kv: -kv[1])
        top, score = ranked[0]
        lead = score - (ranked[1][1] if len(ranked) > 1 else -1.0)
        return top if score >= ICON_SAME and lead >= ICON_LEAD else None

    def learn(self, rgb: np.ndarray, name: str) -> bool:
        """The selected portrait is `name`'s (their 属性详情 says so). False when unsure."""
        at = selected(rgb)
        if at is None or not at.sure:
            return False
        self.keep(name, picture(rgb, at))
        return True

    def keep(self, name: str, learned: np.ndarray) -> None:
        """`name`'s portrait is this picture; a 漂泊者's is the 漂泊者's, whatever the element."""
        self.known[plain(name)] = learned
        self.store.set_setting(KEY, json.dumps(
            {n: base64.b64encode(np.ascontiguousarray(v).tobytes()).decode("ascii")
             for n, v in self.known.items()}, ensure_ascii=False))

    def look(self, rgb: np.ndarray) -> tuple[bool, str | None]:
        """(whether a selected portrait was told, and whose): (False, None) with no column or an
        unsure pick; (True, None) for a portrait never learned."""
        at = selected(rgb)
        if at is None or not at.sure:
            return False, None
        by_icon = self.by_icon(rgb, at)
        if by_icon is not None:
            return True, plain(by_icon)
        scored = [(n, _match(v, rgb, at)) for n, v in self.known.items()]
        if not scored:
            return True, None
        name, score = max(scored, key=lambda kv: kv[1])
        return True, (name if score >= SAME else None)

    def who(self, rgb: np.ndarray) -> str | None:
        return self.look(rgb)[1]
