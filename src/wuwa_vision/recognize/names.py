# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Snap an OCR'd item name onto the official catalogue (D42).

The detail panel's OCR drops or swaps rare characters, and does it at full
confidence: 改造镣环 read as 改造环 (1.00), 梦魇炽枢 as 梦炽枢, 傀儡的秽冕 as
群儡的秽冕, 衍射干涉混悬液 as 行射干涉混悬液. No preprocessing recovered them.
The catalogue (tools/fetch_catalogue.py) lists every real name, so a read that
is one or two characters off a single real name is that name.

Conservative on purpose. A read is snapped only when exactly one catalogue name
is closest and within `max_edits`; a tie is left as read (the user can still fix
it by hand, D40). An exact catalogue name is never changed -- even if it is a
misread of a sibling (低频 vs 中频), nothing in the text can tell.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

CATALOGUE_DIR = Path("data/catalogue")
#: The tab an item entry carries when it is a weapon.
WEAPON_TAB = "武器"


def edit_distance(a: str, b: str) -> int:
    """Levenshtein distance (insert / delete / substitute one character)."""
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def max_edits(name: str) -> int:
    """How far a read may be from a real name: 1, or 2 for names of 8+ characters."""
    return 2 if len(name) >= 8 else 1


def snap(name: str, known: frozenset[str] | set[str]) -> str:
    """The catalogue name `name` is a misread of, or `name` unchanged."""
    if not known or name in known:
        return name
    limit = max_edits(name)
    best: list[str] = []
    best_distance = limit + 1
    for candidate in known:
        if abs(len(candidate) - len(name)) > limit:
            continue
        d = edit_distance(name, candidate)
        if d < best_distance:
            best, best_distance = [candidate], d
        elif d == best_distance:
            best.append(candidate)
    return best[0] if len(best) == 1 else name


@lru_cache(maxsize=4)
def weapon_names(directory: Path = CATALOGUE_DIR) -> frozenset[str]:
    """Every real weapon name (builds.json), or empty without the catalogue.

    A tile on the 武器 tab that shows a level IS a weapon, so a match on anything
    else is a category error however alike the artwork looks (D65).
    """
    names: set[str] = set()
    index = Path(directory) / "index.json"
    if index.exists():
        names |= {
            e["name"] for e in json.loads(index.read_text(encoding="utf-8"))
            if e.get("tab") == WEAPON_TAB
        }
    builds = Path(directory) / "builds.json"
    if builds.exists():
        names |= set(json.loads(builds.read_text(encoding="utf-8")).get("weapons", {}))
    return frozenset(names)


@lru_cache(maxsize=4)
def weapon_types(directory: Path = CATALOGUE_DIR) -> frozenset[str]:
    """The weapon types the catalogue knows (长刃, 迅刀, 佩枪, 臂铠, 音感仪)."""
    builds = Path(directory) / "builds.json"
    if not builds.exists():
        return frozenset()
    data = json.loads(builds.read_text(encoding="utf-8"))
    kinds = {r.get("weapon") for r in data.get("resonators", {}).values()}
    kinds |= {w.get("type") for w in data.get("weapons", {}).values()}
    return frozenset(k for k in kinds if k)


@lru_cache(maxsize=4)
def catalogue_names(directory: Path = CATALOGUE_DIR) -> frozenset[str]:
    """Every real item name, or an empty set when the catalogue is not downloaded."""
    index = Path(directory) / "index.json"
    if not index.exists():
        # No download: the names shipped in the gallery pack (D43).
        from .pack import pack_names

        return pack_names()
    return frozenset(e["name"] for e in json.loads(index.read_text(encoding="utf-8")))
