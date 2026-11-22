# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""A resonator's own screens, read (D270): 属性详情, 技能, 武器, 共鸣链, and the echo bag's panel.

Each screen is known by its title at the top left. Every region is measured in the window's
height from its left or right edge (D9: no pixel constants), so a 21:9 and a 16:10 window read
the same; every region stops above 0.95 of the height -- the UID sits in the bottom 2% at the
right and is never read (AGENTS.md constraint 4).

`read` takes the whole RGB frame and the names a reading snaps onto (the resonators with their
element ids, the echoes, the sets, the weapons), and returns what the screen says, or None when
the frame is not one of these screens.
"""

from __future__ import annotations

import contextvars
import difflib
import functools
import re
from dataclasses import dataclass
from typing import Any

import numpy as np

from . import engine

#: The bottom of every region, as a share of the height: the UID is below 0.98.
BOTTOM = 0.95
ELEMENTS = {"冷凝": 1, "热熔": 2, "导电": 3, "气动": 4, "衍射": 5, "湮灭": 6}
SKILLS = ("常态攻击", "共鸣技能", "共鸣回路", "共鸣解放", "变奏技能")
#: A stat's words on these screens, as 计算's keys (calc_data.STATS). HP/ATK/DEF are a share
#: when the value has a %, an amount when not.
LABELS = {
    "暴击伤害": "crit_dmg",
    "暴击": "crit",
    "共鸣效率": "er",
    "治疗效果加成": "heal",
    "普攻伤害加成": "dmg_basic",
    "重击伤害加成": "dmg_heavy",
    "共鸣技能伤害加成": "dmg_skill",
    "共鸣解放伤害加成": "dmg_lib",
    "冷凝伤害加成": "dmg_1",
    "热熔伤害加成": "dmg_2",
    "导电伤害加成": "dmg_3",
    "气动伤害加成": "dmg_4",
    "衍射伤害加成": "dmg_5",
    "湮灭伤害加成": "dmg_6",
    "生命": "hp",
    "攻击": "atk",
    "防御": "def",
}
_LEVEL = re.compile(r"[Ll][Vv]\.?\s*(\d{1,2})\s*/\s*(\d{1,2})")
_NUMBER = re.compile(r"(\d+(?:\.\d+)?)\s*(%?)")
#: An echo's level on its page, "+25", with up to two stray marks after it ("+25_").
_PLUS = re.compile(r"\+\s*(\d{1,2})\s*[^\d\s]{0,2}")
#: A set's pieces on the 声骸 page, "(2/2)" with either kind of bracket (D340).
_PIECES = re.compile(r"[(（]\s*(\d)\s*/\s*(\d)\s*[)）]?")

#: Where each screen is still enough to be read (D340), as its regions are given: in the height's
#: units from the left edge, or from the right edge when the last is True. Measured on a 3440x1440
#: window, each region's change over 0.1 s (still is under 1.0): the middle, where the model
#: stands, moved 1.52 on 属性详情, 9.29 on 武器, 2.76 on the 声骸 page and 1.33 on the echo list;
#: the panels read, 0.29, 0.41, 0.45 and 0.48. 技能 is read along the bottom, where a glowing
#: arc moves (2.27), but its middle held still (0.68): it keeps the gate's own region (None).
WATCH: dict[str, tuple[float, float, float, float, bool] | None] = {
    "attributes": (0.1, 0.12, 0.62, 0.6, False),
    "weapon": (0.1, 0.12, 0.62, 0.6, False),
    "echoes": (0.1, 0.12, 0.62, 0.6, False),
    "chain": (0.1, 0.12, 0.62, 0.6, False),
    "echo": (0.64, 0.1, 0.0, 0.92, True),
    "skills": None,
}


def watch_roi(kind: str | None, w: int, h: int) -> tuple[float, float, float, float]:
    """The region the frame gate watches on this screen, as the gate takes it: shares of the
    width and of the height. The gate's own region for the bag and for a screen not listed."""
    from ..capture.gating import DEFAULT_ROI

    said = WATCH.get(kind or "")
    if said is None:
        return DEFAULT_ROI
    left, top, right, bottom, from_right = said
    x0, x1 = (w - left * h, w - right * h) if from_right else (left * h, right * h)
    return (max(0.0, x0 / w), top, min(1.0, x1 / w), bottom)


@dataclass
class Line:
    """One piece of text, its box in the frame in units of the frame's height."""

    x0: float
    y0: float
    x1: float
    y1: float
    text: str

    @property
    def mid(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2


@functools.cache
def _ocr() -> Any:
    return engine._engine()


#: The lines read while `read_with_boxes` runs, for the scan's pages to draw (D343).
_SEEN: contextvars.ContextVar[list | None] = contextvars.ContextVar("seen", default=None)


def read_with_boxes(rgb: np.ndarray, **kwargs: Any) -> tuple[dict | None, list[Line]]:
    """`read`, and every line of text it read on the way: where each was, and what it said."""
    token = _SEEN.set([])
    try:
        return read(rgb, **kwargs), list(_SEEN.get() or [])
    finally:
        _SEEN.reset(token)


def _lines(
    rgb: np.ndarray,
    left: float,
    top: float,
    right: float,
    bottom: float,
    *,
    from_right: bool = False,
) -> list[Line]:
    """The text in a region given in units of the height: x from the left edge, or from the
    right edge when `from_right` (then `left` is the farther edge)."""
    h, w = rgb.shape[:2]
    bottom = min(bottom, BOTTOM)
    if from_right:
        x0, x1 = w - int(left * h), w - int(right * h)
    else:
        x0, x1 = int(left * h), int(right * h)
    x0, x1 = max(0, x0), min(w, x1)
    y0, y1 = int(top * h), int(bottom * h)
    if x1 <= x0 or y1 <= y0:
        return []
    result, _ = _ocr()(np.ascontiguousarray(rgb[y0:y1, x0:x1]))
    out = []
    for points, text, _conf in result or []:
        xs = [p[0] + x0 for p in points]
        ys = [p[1] + y0 for p in points]
        out.append(Line(min(xs) / h, min(ys) / h, max(xs) / h, max(ys) / h, str(text).strip()))
    seen = _SEEN.get()
    if seen is not None:
        seen.extend(out)
    return sorted(out, key=lambda line: (line.y0, line.x0))


def _snap(text: str, names: list[str] | tuple[str, ...], cutoff: float = 0.5) -> str | None:
    if not text or not names:
        return None
    if text in names:
        return text
    plain = text.replace("・", "·").replace(".", "·")
    if plain in names:
        return plain
    found = difflib.get_close_matches(plain, list(names), n=1, cutoff=cutoff)
    return found[0] if found else None


def _value(text: str) -> tuple[float, bool] | None:
    found = _NUMBER.search(text.replace(",", ""))
    if not found:
        return None
    number = float(found.group(1))
    return (number / 100, True) if found.group(2) else (number, False)


def _one_off(words: str) -> str | None:
    """The one label that `words` (or its end) misses by a single character, as OCR slips on
    衍射 -> "行射"; None when none or several do. Labels under four characters never: 生命, 攻击
    and 防御 are one character from far too much."""
    fits = {
        key
        for label, key in LABELS.items()
        if len(label) >= 4
        and len(words) >= len(label)
        and sum(a != b for a, b in zip(words[-len(label):], label, strict=True)) == 1
    }
    return fits.pop() if len(fits) == 1 else None


def _stat(label: str, value: str) -> dict | None:
    words = re.sub(r"^[+＋十·\s]+", "", label).strip()
    within = [k for w, k in sorted(LABELS.items(), key=lambda kv: -len(kv[0])) if w in words]
    long = [k for w, k in LABELS.items() if len(w) >= 4 and w in words]
    # a whole long label first, then one a character off ("暴击伤舍" is 暴击伤害, not 暴击)
    key = LABELS.get(words) or (long[0] if long else None) or _one_off(words) or next(
        iter(within), None
    )
    said = _value(value)
    if key is None or said is None:
        return None
    number, share = said
    if key in ("hp", "atk", "def"):
        return {"stat": f"{key}_pct" if share else key, "value": number}
    return {"stat": key, "value": number if share else number}


def _rows(lines: list[Line], until: float = 9.0) -> list[dict]:
    """Stat rows: a label and the value on the same line to its right, above `until`."""
    out = []
    labels = [
        line
        for line in lines
        if line.y0 < until and re.search(r"[一-鿿]", line.text) and not _value(line.text)
    ]
    for label in labels:
        same = [
            v
            for v in lines
            if v is not label
            and abs(v.mid - label.mid) < 0.015
            and v.x0 > label.x1
            and _value(v.text)
            and not re.search(r"[一-鿿]", v.text)
        ]
        if not same:
            continue
        said = _stat(label.text, min(same, key=lambda v: v.x0 - label.x1).text)
        if said:
            out.append(said)
    return out


def kind_of(rgb: np.ndarray) -> str | None:
    """Which screen this is, from the title at the top left; None for anything else."""
    title = " ".join(line.text for line in _lines(rgb, 0, 0, 0.6, 0.11))
    if "COST" in title.upper() or "全部" in title:
        return "echo"
    if "属性" in title:
        return "attributes"
    if "共鸣链" in title or "鸣链" in title:
        return "chain"
    if "技能" in title:
        return "skills"
    if "声骸" in title:
        return "echoes"
    if "武器" in title or "器" in title:
        # the bag's 武器 tab says 武器 too: a weapon screen has a level and a rank ("N阶")
        panel = [line.text for line in _lines(rgb, 0.1, 0.12, 0.62, 0.6)]
        if any(_LEVEL.search(t) for t in panel) and any(re.match(r"\s*\d\s*阶", t) for t in panel):
            return "weapon"
    return None


def read(
    rgb: np.ndarray,
    *,
    names: dict[str, int] | None = None,
    echoes: list[str] | None = None,
    sets: list[str] | None = None,
    weapons: list[str] | None = None,
    kind: str | None = None,
) -> dict | None:
    """What this screen says, or None when it is not a resonator's screen (D270). `kind`: the
    screen, when it is known already (`ocr.screen`, D331) -- its title is then not read again."""
    kind = kind or kind_of(rgb)
    if kind is None:
        return None
    if kind == "attributes":
        return _attributes(rgb, names or {})
    if kind == "skills":
        return _skills(rgb)
    if kind == "weapon":
        return _weapon(rgb, weapons or [])
    if kind == "echo":
        return _echo(rgb, names or {}, echoes or [], sets or [])
    if kind == "echoes":
        return _worn(rgb, sets or [])
    return {"kind": kind}


def _by_row(lines: list[Line]) -> list[list[Line]]:
    """Lines on one row together, top to bottom, each row left to right."""
    rows: list[list[Line]] = []
    for line in sorted(lines, key=lambda x: x.mid):
        if rows and abs(rows[-1][0].mid - line.mid) < 0.012:
            rows[-1].append(line)
        else:
            rows.append([line])
    return [sorted(row, key=lambda x: x.x0) for row in rows]


def _worn(rgb: np.ndarray, sets: list[str]) -> dict:
    """A resonator's 声骸 page (D340): what they wear. The totals the echoes give, the main
    echo's skill (its words), and each set with the pieces worn of the most that count. The
    page does not name them: it is the last 属性详情's resonator's, as 技能 and 武器 are."""
    rows = _by_row(_lines(rgb, 0.1, 0.12, 0.62, 0.85))
    words = [" ".join(line.text for line in row) for row in rows]
    skill_at = next((i for i, w in enumerate(words) if "声骸技能" in w), len(rows))
    sets_at = next((i for i, w in enumerate(words) if "合鸣效果" in w), len(rows))
    stats: dict[str, str] = {}
    for row in rows[:skill_at]:
        label = next((line.text for line in row if line.text in LABELS), None)
        value = next((line.text for line in row if _value(line.text) is not None), None)
        if label and value:
            stats[label] = value.replace(" ", "")
    skill = "".join(words[skill_at + 1 : sets_at]).replace(" ", "")
    worn: list[dict] = []
    for text in words[sets_at + 1 :]:
        pieces = _PIECES.search(text)
        if not pieces:
            continue
        name = re.sub(r"[^一-鿿]", "", text[: pieces.start()])
        found = _snap(name, sets)
        if not found:
            continue
        said = {"name": found, "pieces": int(pieces.group(1)), "of": int(pieces.group(2))}
        # a set of five lists its 2-piece and its 5-piece rows: the most pieces is what is worn
        had = next((s for s in worn if s["name"] == found), None)
        if had is None:
            worn.append(said)
        elif said["pieces"] > had["pieces"]:
            had.update(said)
    return {"kind": "echoes", "sets": worn, "stats": stats, "skill": skill}


#: The player's resonator: one name on screen, one form per element in the names (D370).
ROVER = "漂泊者"


def _person(text: str, element: int | None, names: dict[str, int]) -> str | None:
    if text in names:
        return text
    if "漂泊" in text:
        # the 漂泊者's form is their element's; with the element not read, which form is not
        # known, and is not guessed (D370)
        form = next((n for n, e in names.items() if n.startswith(ROVER) and e == element), None)
        return form if element is not None and form else ROVER
    pool = [n for n, e in names.items() if element is None or e == element]
    # a name read short ("锁") is the one of its element that starts with it
    starts = [n for n in pool if text and n.startswith(text)]
    if len(starts) == 1:
        return starts[0]
    return _snap(text, pool, cutoff=0.4)


def _attributes(rgb: np.ndarray, names: dict[str, int]) -> dict:
    lines = _lines(rgb, 0.1, 0.12, 0.62, 0.6)
    element = next((ELEMENTS[line.text] for line in lines if line.text in ELEMENTS), None)
    level = next((m for line in lines if (m := _LEVEL.search(line.text))), None)
    top = next((line.y0 for line in lines if _LEVEL.search(line.text)), 0.3)
    name_line = next(
        (
            line
            for line in reversed(lines)
            if line.y1 <= top + 0.005
            and line.text not in ELEMENTS
            and re.search(r"[一-鿿]", line.text)
        ),
        None,
    )
    said = _rows(lines)
    stats = {s["stat"].removesuffix("_pct"): s["value"] for s in said}
    person = _person(name_line.text, element, names) if name_line else None
    return {
        "kind": "attributes",
        "name": person,
        # the element's word was not read: the resonator's own is known
        "element": element if element is not None else names.get(person or ""),
        "level": int(level.group(1)) if level else None,
        "cap": int(level.group(2)) if level else None,
        "stats": stats,
    }


def _skills(rgb: np.ndarray) -> dict:
    h, w = rgb.shape[:2]
    lines = _lines(rgb, 0.3, 0.6, w / h - 0.5, 0.95)
    levels = [(line, m) for line in lines if (m := _LEVEL.search(line.text))]
    out: dict[str, int] = {}
    for line in lines:
        name = next((s for s in SKILLS if s in line.text), None)
        if name is None:
            continue
        above = [
            (lv, m)
            for lv, m in levels
            if 0 <= line.y0 - lv.y0 < 0.07 and abs(lv.cx - line.cx) < 0.08
        ]
        if above:
            out[name] = int(min(above, key=lambda pair: line.y0 - pair[0].y0)[1].group(1))
    grey = rgb.mean(axis=2) if rgb.ndim == 3 else rgb.astype(np.float32)
    rings: dict[str, list[float | None]] = {}
    for line in lines:
        name = next((s for s in SKILLS if s in line.text), None)
        if name is not None and name not in rings:
            rings[name] = [_ring(grey, (line.x0 + line.x1) / 2 + dx, line.y0 - dy)
                           for dx, dy in NODES.get(name, NODES["stat"])]
    said = {"kind": "skills", "skills": {s: out[s] for s in SKILLS if s in out}}
    # no node seen at all: the tree is not on this frame, and nothing is said of it
    if any(r is not None and r > NODE_SEEN for shown in rings.values() for r in shown):
        said["nodes"] = {s: [_taken(r) for r in rings[s]] for s in SKILLS if s in rings}
    return said


#: Where a skill's two nodes sit (D358), lowest first -- the one taken first: across from the
#: middle of its name and above its top, in the window's height. 共鸣回路's are its 固有技能,
#: diamonds a little lower than the others' round stat nodes. Measured on the user's 3440x1440
#: window; the same on every resonator's screen.
NODES = {"stat": ((-0.007, 0.345), (-0.007, 0.55)), "共鸣回路": ((0.0, 0.335), (0.0, 0.545))}
#: A node's ring at 60% brightness: taken 240-250, not taken 45-128 (D358). Between the two
#: it is not told (None) rather than guessed.
NODE_TAKEN, NODE_NOT_TAKEN = 215.0, 160.0
#: The sky beside the nodes read 21-49, a grey stat node not taken 87-89 (D358): a frame where no
#: node is brighter than this shows no tree (a padlocked 固有技能, 45, is not taken all the same).
NODE_SEEN = 60.0


def _ring(grey: np.ndarray, x: float, y: float) -> float | None:
    """How bright the ring round a node is, its centre at (x, y) in the height's units; None
    outside the window."""
    h, w = grey.shape[:2]
    px, py = x * h, y * h
    r0, r1 = 0.010 * h, 0.019 * h
    x0, x1, y0, y1 = int(px - r1), int(px + r1) + 1, int(py - r1), int(py + r1) + 1
    if x0 < 0 or y0 < 0 or x1 > w or y1 > h:
        return None
    yy, xx = np.ogrid[y0:y1, x0:x1]
    far = np.hypot(yy - py, xx - px)
    return float(np.percentile(grey[y0:y1, x0:x1][(far >= r0) & (far <= r1)], 60))


def _taken(level: float | None) -> bool | None:
    """A white disc is taken, a grey one not; between the two, or not seen, is not told."""
    if level is None:
        return None
    if level >= NODE_TAKEN:
        return True
    if level <= NODE_NOT_TAKEN:
        return False
    return None


def _weapon(rgb: np.ndarray, weapons: list[str]) -> dict:
    lines = _lines(rgb, 0.1, 0.12, 0.62, 0.6)
    level = next((m for line in lines if (m := _LEVEL.search(line.text))), None)
    at = next((line.y0 for line in lines if _LEVEL.search(line.text)), 0.3)
    name_line = next(
        (
            line
            for line in reversed(lines)
            if line.y1 <= at + 0.005 and re.search(r"[一-鿿]", line.text)
        ),
        None,
    )
    rank = next(
        (int(m.group(1)) for line in lines if (m := re.match(r"\s*(\d)\s*阶", line.text))), None
    )
    until = next((line.y0 for line in lines if re.match(r"\s*\d\s*阶", line.text)), 9.0)
    stats = {s["stat"]: s["value"] for s in _rows(lines, until)}
    return {
        "kind": "weapon",
        "name": (_snap(name_line.text, weapons) or name_line.text) if name_line else None,
        "level": int(level.group(1)) if level else None,
        "cap": int(level.group(2)) if level else None,
        "rank": rank,
        "stats": stats,
    }


def _echo(rgb: np.ndarray, names: dict[str, int], echoes: list[str], sets: list[str]) -> dict:
    lines = _lines(rgb, 0.64, 0.1, 0.0, 0.92, from_right=True)
    skill_at = next((line.y0 for line in lines if "声骸技能" in line.text), 9.0)
    # "+25", or with a stray mark after it as OCR reads one at times ("+25_", the live scan)
    plus = next((line for line in lines if re.fullmatch(_PLUS, line.text)), None)
    cost = next(
        # "COST 4", or with a stray mark between as OCR reads one at times ("COST.4", D359)
        (int(m.group(1)) for line in lines
         if (m := re.search(r"COST[\s.:·,_-]{0,2}(\d)", line.text.upper()))),
        None,
    )
    name_line = next(
        (
            line
            for line in lines
            if line.y0 < (plus.y1 if plus else 0.2) and re.search(r"[一-鿿]", line.text)
        ),
        None,
    )
    rows = _rows([line for line in lines if not re.search(r"COST", line.text.upper())], skill_at)
    set_name = None
    for line in lines:
        if re.search(r"\(\s*\d\s*/\s*\d\s*\)", line.text) or re.fullmatch(
            r"\(?\d/\d\)?", line.text
        ):
            words = [
                o
                for o in lines
                if abs(o.mid - line.mid) < 0.015
                and o.x1 <= line.x0 + 0.01
                and re.search(r"[一-鿿]", o.text)
            ]
            text = (words[0].text if words else re.sub(r"\(.*", "", line.text)).strip()
            set_name = _snap(text, sets) or set_name or text or None
            if set_name:
                break
    holder = next(
        (
            line.text.removesuffix("装配中").strip()
            for line in lines
            if line.text.endswith("装配中")
        ),
        None,
    )
    # the level is its own "+25", or read on the end of the name's line
    level = int(re.fullmatch(_PLUS, plus.text).group(1)) if plus else None
    named = name_line.text if name_line else None
    if named and level is None and (joined := re.search(r"\s*\+\s*(\d{1,2})\s*$", named)):
        level, named = int(joined.group(1)), named[: joined.start()]
    return {
        "kind": "echo",
        "name": (_snap(named, echoes) or named) if named else None,
        "level": level,
        "cost": cost,
        "main": rows[:2],
        "subs": rows[2:],
        "set": set_name,
        "holder": (_person(holder, None, names) or holder) if holder else None,
    }
