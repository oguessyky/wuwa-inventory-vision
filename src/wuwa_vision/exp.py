# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Level EXP: what a resonator or weapon needs, and which EXP items pay it (D52).

EXP needed comes from the game's level tables (tools/fetch_levels.py ->
levels.json): a resonator's EXP to reach each level, a weapon's EXP from each
level to the next per rarity. The EXP items and their values come from the
catalogue itself -- 共鸣者经验材料 (共鸣促剂) and 武器经验材料 (能源核心), each page
saying how much it gives ("可为共鸣者增加3000点经验").

The user asked for the payment per item tier (D52): `mix` spends what is owned,
biggest first without overshooting, then covers any remainder with the smallest
owned item that fills it, and states what is still missing as items of the
biggest tier.

Headless: the main app renders what this returns.
"""

from __future__ import annotations

import json
import math
import re

from .catalogue import Catalogue

#: Level cap after each ascension (0 = not ascended yet).
CAPS = (20, 40, 50, 60, 70, 80, 90)
#: 类型 of the EXP items, per kind of build.
EXP_TYPE = {"resonator": "共鸣者经验材料", "weapon": "武器经验材料", "echo": "声骸养成材料"}
#: What "a full one" is per kind: (rarity, from level, to level, label).
FULL = {"resonator": (5, 1, 90, "一位共鸣者 1 → 90"),
        "weapon": (5, 1, 90, "一把五星武器 1 → 90"),
        "echo": (5, 0, 25, "一个五星声骸 0 → 25")}
#: The levels a build is counted to, per kind (D157). An echo opens one 辅音 slot
#: every five levels, and those are the steps a player stops at; a resonator and a
#: weapon are counted to the top only, as `FULL` has them.
TIERS = {"resonator": (90,), "weapon": (90,), "echo": (5, 10, 15, 20, 25)}
_AMOUNT = re.compile(r"(\d{3,6})\s*点?经验")


def tables(catalogue: Catalogue) -> dict:
    """levels.json, or {} before tools/fetch_levels.py has run."""
    cached = catalogue.__dict__.get("_levels")
    if cached is None:
        path = catalogue.directory / "levels.json"
        cached = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        catalogue.__dict__["_levels"] = cached
    return cached


def items(catalogue: Catalogue, kind: str) -> list[dict]:
    """The EXP items for `kind`, biggest first: {name, value, rarity, icon_file}."""
    out = []
    for name in catalogue.names():
        page = catalogue.page(name)
        if (page.get("类型") or "").strip() != EXP_TYPE[kind]:
            continue
        amount = _AMOUNT.search((page.get("功能") or "") + (page.get("描述") or ""))
        if amount:
            out.append({"name": name, "value": int(amount.group(1)),
                        "rarity": (catalogue.entry(name) or {}).get("rarity") or 0,
                        "icon_file": catalogue.icon_file(name)})
    return sorted(out, key=lambda i: -i["value"])


def needed(catalogue: Catalogue, kind: str, rarity: int, level_from: int,
           level_to: int) -> int:
    """EXP from `level_from` to `level_to` (0 when the table is missing or it is
    already there)."""
    data = tables(catalogue)
    if level_to <= level_from or not data:
        return 0
    if kind == "resonator":  # entry L = EXP to reach L
        table = data.get("resonator") or []
        return sum(table[level_from + 1:level_to + 1])
    if kind == "echo":  # entry L = EXP to reach L; group = rarity - 1 (5-star: +25)
        table = (data.get("echo") or {}).get(str(max((rarity or 5) - 1, 1))) or []
        return sum(table[level_from + 1:level_to + 1])
    table = (data.get("weapon") or {}).get(str(rarity or 5)) or []
    return sum(table[level_from:level_to])  # entry L = EXP from L to L+1


def shells_for(catalogue: Catalogue, kind: str, exp: int) -> int:
    """贝币 that feeding `exp` costs (weapons only: resonator potions cost none)."""
    rate = tables(catalogue).get("weapon_shells_per_exp") if kind == "weapon" else None
    return round(exp * rate) if rate else 0


def mix(need: int, stock: list[dict], owned: dict[str, int]) -> dict:
    """Which EXP items pay `need`, per tier.

    Biggest first, never overshooting; a remainder is then covered by the smallest
    owned item big enough (a little EXP is wasted, as in the game); what is still
    missing is counted in items of the biggest tier.
    """
    left = need
    rows = [{**i, "owned": owned.get(i["name"], 0), "use": 0, "short": 0} for i in stock]
    for row in rows:  # biggest first
        take = min(row["owned"], left // row["value"])
        row["use"] += take
        left -= take * row["value"]
    if left > 0:
        for row in reversed(rows):  # smallest item that still covers the rest
            if row["owned"] - row["use"] > 0 and row["value"] >= left:
                row["use"] += 1
                left = 0
                break
    if left > 0:
        for row in reversed(rows):  # no single item covers it: pile up small ones
            spare = row["owned"] - row["use"]
            take = min(spare, math.ceil(left / row["value"]))
            row["use"] += take
            left = max(left - take * row["value"], 0)
            if not left:
                break
    if left > 0 and rows:
        rows[0]["short"] = math.ceil(left / rows[0]["value"])
    return {"needed": need, "items": rows, "missing": left,
            "shortfall": sum(r["short"] for r in rows)}


def kind_of(catalogue: Catalogue, name: str) -> str | None:
    """Which kind of build an EXP item feeds, or None for anything else."""
    kind = next((k for k, t in EXP_TYPE.items()
                 if (catalogue.page(name).get("类型") or "").strip() == t), None)
    return kind if kind and any(i["name"] == name for i in items(catalogue, kind)) else None


def tiers(catalogue: Catalogue, kind: str, points: int) -> list[dict]:
    """How many of a kind `points` EXP take to each of its tiers (D157): per tier
    {to, need, count}. Each is its own answer to "if all of it went there" --
    they are not shares of one stock. Counted in EXP and nothing else: not 贝币,
    not 调谐器. A plain division, like `fulls`: the little EXP lost when a big
    item overshoots is not taken off. A level the table does not reach is left out."""
    rarity, low, _high, _label = FULL[kind]
    top = reach(catalogue, kind, rarity)
    out = []
    for level in TIERS[kind]:
        need = needed(catalogue, kind, rarity, low, level) if level <= top else 0
        if need:
            out.append({"to": level, "need": need, "count": points // need})
    return out


def reach(catalogue: Catalogue, kind: str, rarity: int) -> int:
    """The highest level the table for `kind` goes to (0 with no table). `needed`
    sums what it finds, so a table cut short would pass for the whole climb."""
    data = tables(catalogue)
    if kind == "resonator":
        return max(len(data.get("resonator") or []) - 1, 0)
    if kind == "echo":
        return max(len((data.get("echo") or {}).get(str(max((rarity or 5) - 1, 1))) or []) - 1, 0)
    return len((data.get("weapon") or {}).get(str(rarity or 5)) or [])  # entry L: from L to L+1


def worth(catalogue: Catalogue, name: str, owned: dict[str, int]) -> dict | None:
    """For an EXP item's hover and panel: how many make a full one, and how many
    full ones everything owned of its kind pays for (D52 follow-up) -- and, tier
    by tier, how many it takes that far (`tiers`, D157)."""
    kind = kind_of(catalogue, name)
    if kind is None:
        return None
    rarity, low, high, label = FULL[kind]
    full = needed(catalogue, kind, rarity, low, high)
    stock = items(catalogue, kind)
    value = next(i["value"] for i in stock if i["name"] == name)
    points = sum(i["value"] * owned.get(i["name"], 0) for i in stock)
    return {"kind": kind, "label": label, "value": value, "full": full,
            "icon_file": catalogue.icon_file(name),
            "count_for_full": math.ceil(full / value) if full else None,
            "owned_points": points, "fulls": points // full if full else None,
            "tiers": tiers(catalogue, kind, points),
            "mix": mix(full, stock, owned) if full else None}


def cost(catalogue: Catalogue, kind: str, rarity: int, level_from: int, level_to: int,
         owned: dict[str, int]) -> dict | None:
    """Everything a build's EXP takes: points, the item mix, 贝币 (weapons)."""
    need = needed(catalogue, kind, rarity, level_from, level_to)
    if not need:
        return None
    return {**mix(need, items(catalogue, kind), owned),
            "shells": shells_for(catalogue, kind, need),
            "levels": [level_from, level_to]}
