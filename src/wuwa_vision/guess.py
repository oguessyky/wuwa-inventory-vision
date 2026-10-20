# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""猜谜: guess the resonator from what the catalogue knows about them (D147).

One resonator is the answer. Each guess is laid out as ten things the catalogue
holds for every resonator -- 属性, 武器, 实装版本, 出生, 所属, what their own dish
does, and the four materials only some builds share -- and the answer to a guess
is how those compare with the answer's. How many of them are compared, and how
much of the comparison is told, is the level:

    普通   all ten; each is right, partly right, or wrong; 版本 says which way
    困难   eight (no 版本, no dish); each is right or wrong
    噩梦   the same eight; one number: how many of them are right

Nothing here is a table of resonators. Every value is read out of the build the
wiki gave, so a resonator joins the day the catalogue has a version and a build
for them, and one the wiki says 未知 about is compared on that word like any other.

There is one answer a day, picked from the date alone, so every machine showing
the same catalogue agrees on it without anything being sent anywhere.
"""

from __future__ import annotations

import hashlib
import random
from datetime import date, datetime, timedelta

from pypinyin import lazy_pinyin

from . import effects, materials, roster, search
from .catalogue import Catalogue

#: A level and how many guesses it allows.
LEVELS = {"普通": 5, "困难": 6, "噩梦": 10}
DEFAULT_LEVEL = "普通"
#: The level that answers with a count and nothing else.
BLIND = "噩梦"
#: What a guess is compared on, in the order the page shows it.
COLUMNS = ("element", "weapon", "version", "birthplace", "faction",
           "dish", "weekly", "boss", "flower", "enemy")
#: What a harder level leaves out: the two that can be partly right, and so say most.
HARD_WITHOUT = ("version", "dish")
#: Columns read out of the build's materials: column -> `materials.slot_of`.
_SLOTS = ("weekly", "boss", "flower", "enemy")
#: What a column says when the wiki says nothing: a value, compared like any other.
NONE = "无"
#: The game's day turns at four in the morning; so does this one.
DAY_TURNS_AT = 4
MODES = ("daily", "free")
#: What a player may write on a cell of a 噩梦 row: their own note, never checked.
NOTES = ("hit", "miss")

#: The clock, for the day and nothing else. A test puts its own here.
clock = datetime.now


def columns(level: str) -> tuple[str, ...]:
    """The columns a round at `level` has."""
    if level == DEFAULT_LEVEL:
        return COLUMNS
    return tuple(c for c in COLUMNS if c not in HARD_WITHOUT)


def today(now: datetime | None = None) -> date:
    """The game's day: before 04:00 it is still yesterday."""
    return ((now or clock()) - timedelta(hours=DAY_TURNS_AT)).date()


def _same(name: str) -> str:
    """One 漂泊者 form whatever the gender: 漂泊者-女-衍射 and 漂泊者-男-衍射 are
    the same row here, and a save has only one of them (D72)."""
    if not roster.is_rover(name):
        return name
    return f"{roster.ROVER}-{name.rsplit('-', 1)[-1]}"


def pool(catalogue: Catalogue, gender: str | None = None) -> list[str]:
    """Who can be guessed, and be the answer: everyone the catalogue has a version
    and a build for, the 漂泊者 once per element in the save's own gender (男 until
    the save says, as its face is everywhere else)."""
    gender = gender if gender in roster.GENDERS else roster.GENDERS[-1]
    out = []
    for name, build in catalogue.builds.get("resonators", {}).items():
        if not build.get("version") or not build.get("materials"):
            continue
        if roster.is_rover(name) and f"-{gender}-" not in name:
            continue
        out.append(name)
    return out


def _dish(catalogue: Catalogue, name: str, build: dict) -> str | None:
    """Their own dish: the one only they cook, else the one the wiki names."""
    own = roster.signature_dishes(catalogue).get(name) or []
    dish = own[0]["name"] if own else (build.get("dish") or "").strip()
    return dish if dish and dish != NONE else None


def place_icon(catalogue: Catalogue, place: str) -> str | None:
    """A picture for a place, when this machine has been given one.

    Nothing fetches these and none ship (the wiki has no picture of a region): it
    is a file the user puts among the avatars, named for the place in pinyin --
    `region-huanglong.webp` for 瑝珑 -- and the cell draws it beside the name."""
    said = "".join(lazy_pinyin(place)).lower()
    stem = "region-" + "".join(c for c in said if c.isascii() and c.isalnum())
    if stem == "region-":
        return None
    here = catalogue.files_in("avatars")
    return next((f"{stem}.{ext}" for ext in ("webp", "png") if f"{stem}.{ext}" in here), None)


def _material(catalogue: Catalogue, name: str) -> dict:
    role, drop = materials.role_of(catalogue, name)
    return {"name": name, "icon_file": catalogue.icon_file(name),
            "drop": drop, "drop_icon": catalogue.bosses.get(drop or "")}


def clues(catalogue: Catalogue, name: str) -> dict[str, dict]:
    """The ten things `name` is compared on. Each is {"values": [...]} -- what is
    compared, one value or a few -- and whatever a page needs to draw it."""
    cached = catalogue.__dict__.setdefault("_guess_clues", {})
    if name in cached:
        return cached[name]
    build = catalogue.builds.get("resonators", {}).get(name) or {}
    icons = roster.badges(catalogue, build)
    out: dict[str, dict] = {
        "element": {"values": [build.get("element") or NONE], "icon": icons["el_icon"]},
        "weapon": {"values": [build.get("weapon") or NONE], "icon": icons["wp_icon"]},
        "version": {"values": [(build.get("version") or NONE).lstrip("Vv")]},
        "birthplace": {"values": [(build.get("birthplace") or NONE).strip()]},
        "faction": {"values": [(build.get("faction") or NONE).strip()]},
    }
    out["birthplace"]["icon"] = place_icon(catalogue, out["birthplace"]["values"][0])
    dish = _dish(catalogue, name, build)
    effect = effects.parse(catalogue.page(dish).get("功能")) if dish else None
    out["dish"] = {"values": sorted({s.tag for s in effect.stats}) if effect else [],
                   "name": dish, "icon_file": catalogue.icon_file(dish) if dish else None}
    out["dish"]["values"] = out["dish"]["values"] or [NONE]
    by_slot: dict[str, list[str]] = {slot: [] for slot in _SLOTS}
    for material in build.get("materials") or {}:
        slot = materials.slot_of(catalogue, material)
        if slot == "enemy":
            # the family, by its highest tier: all four tiers are one answer
            material = (materials.family(catalogue, material) or [material])[-1]
        if slot in by_slot and material not in by_slot[slot]:
            by_slot[slot].append(material)
    for slot, names in by_slot.items():
        out[slot] = {"values": sorted(names) or [NONE],
                     "items": [_material(catalogue, n) for n in sorted(names)]}
    cached[name] = out
    return out


def _major(version: str) -> str:
    return version.split(".")[0]


def compare(guess: dict[str, dict], answer: dict[str, dict],
            over: tuple[str, ...] = COLUMNS) -> dict[str, dict]:
    """Column by column: {"mark": hit | near | miss} and, for 版本, which way the
    answer lies ("later" / "earlier"). Near is said only where the values can be
    partly the same: a few of several shared, or the same major version.

    The dish is the one column that is not compared on what the cell says. The
    cell says what the dish does; right means the same DISH, which only the
    answer has (or neither having one), and a different dish that does the same
    thing -- or one of the same things -- is partly right."""
    out: dict[str, dict] = {}
    for column in over:
        mine, theirs = guess[column]["values"], answer[column]["values"]
        if column == "dish":
            if guess[column]["name"] == answer[column]["name"]:
                out[column] = {"mark": "hit"}
            else:
                shared = set(mine) & set(theirs) - {NONE}
                out[column] = {"mark": "near" if shared else "miss"}
        elif mine == theirs:
            out[column] = {"mark": "hit"}
        elif column == "version":
            both = roster._version(mine[0]), roster._version(theirs[0])
            near = bool(both[0] and both[1]) and _major(mine[0]) == _major(theirs[0])
            out[column] = {"mark": "near" if near else "miss"}
            if both[0] and both[1]:
                out[column]["way"] = "later" if both[1] > both[0] else "earlier"
        else:
            shared = set(mine) & set(theirs) - {NONE}
            out[column] = {"mark": "near" if shared else "miss"}
    return out


def told(level: str, marks: dict[str, dict]) -> dict:
    """What a level says of a compared guess: the marks, fewer of them, or a count."""
    hits = sum(1 for m in marks.values() if m["mark"] == "hit")
    if level == BLIND:
        return {"hits": hits}
    if level == "困难":
        return {"marks": {c: {"mark": "hit" if m["mark"] == "hit" else "miss"}
                          for c, m in marks.items()}}
    return {"marks": marks}


def _order(names: list[str], turn: int) -> list[str]:
    """`names` shuffled, the same way for everyone, differently every `turn`."""
    return sorted(names, key=lambda n: hashlib.sha256(f"{turn}:{n}".encode()).digest())


def daily_answer(catalogue: Catalogue, day: date, gender: str | None = None) -> str | None:
    """The day's resonator. Everyone has a turn before anyone has a second: the
    pool is dealt out in an order that only the date decides, and dealt again
    when it runs out. The gender picks which 漂泊者 is named, never who it is."""
    names = pool(catalogue, gender)
    if not names:
        return None
    same = sorted({_same(n) for n in names})
    turn, place = divmod(day.toordinal(), len(same))
    picked = _order(same, turn)[place]
    return next(n for n in names if _same(n) == picked)


def free_answer(catalogue: Catalogue, gender: str | None, avoid: set[str],
                rng: random.Random | None = None) -> str | None:
    """Anyone, for a round that does not count -- but not `avoid` (the day's own
    answer, which a free round must not give away, and the round just played)."""
    names = pool(catalogue, gender)
    names = [n for n in names if _same(n) not in {_same(a) for a in avoid}] or names
    return (rng or random).choice(names) if names else None


def person(catalogue: Catalogue, name: str) -> dict:
    """A resonator as the page lists and names them."""
    build = catalogue.builds.get("resonators", {}).get(name) or {}
    return {"name": name, "english": english(name, build), "rarity": build.get("rarity") or 0,
            "find": search.keys(name, catalogue.english(name) or build.get("english") or ""),
            "icon": catalogue.avatar_file(name), "card": roster._art(catalogue, build.get("card"))}


def english(name: str, build: dict) -> str:
    """The wiki's English name, written the way a name is written: it has
    "CHANGLI", "Jingran" and "YangyangXuanling" for three resonators."""
    raw = (build.get("english") or "").strip()
    if not raw:
        return ""
    if raw.isupper():
        raw = raw.title()
    else:  # words run together: a capital inside a word starts the next one
        raw = "".join(" " + c if c.isupper() and i and raw[i - 1].islower() else c
                      for i, c in enumerate(raw))
    return raw


def people(catalogue: Catalogue, gender: str | None = None) -> list[dict]:
    return [person(catalogue, name) for name in pool(catalogue, gender)]


def row(catalogue: Catalogue, level: str, guess: str, answer: str, over: bool = False) -> dict:
    """One guess as the page shows it: who, their values in the level's columns,
    and what the level says of them. Once the round is `over` there is nothing
    left to keep back, so a 噩梦 row says which of its cells were the right ones."""
    mine = clues(catalogue, guess)
    marks = compare(mine, clues(catalogue, answer), columns(level))
    said = told(level, marks)
    if over and level == BLIND:
        said = {**said, **told("困难", marks)}
    right = _same(guess) == _same(answer)
    return {**person(catalogue, guess), "cells": {c: mine[c] for c in columns(level)}, **said,
            "right": right,
            # with two columns gone, two resonators can be the same in every one left
            "twin": not right and all(m["mark"] == "hit" for m in marks.values())}


def view(catalogue: Catalogue, round_: dict | None, level: str) -> dict:
    """A round for the page. The answer is in it only once the round is over.

    `round_` is the saved row (`Store.guess_round`) or None before the first
    guess, when `level` is the one that would be played."""
    if not round_:
        return {"level": level, "tries": LEVELS[level], "columns": list(columns(level)),
                "rows": [], "notes": {}, "result": None, "answer": None, "started": False}
    level, answer = round_["level"], round_["answer"]
    known = catalogue.builds.get("resonators", {})
    over = round_["result"] is not None
    rows = [row(catalogue, level, g, answer, over) for g in round_["guesses"] if g in known]
    theirs = clues(catalogue, answer) if over and answer in known else None
    return {"level": level, "tries": LEVELS[level], "columns": list(columns(level)),
            "rows": rows, "notes": round_["notes"], "result": round_["result"], "started": True,
            "answer": {**person(catalogue, answer),
                       "cells": {c: theirs[c] for c in columns(level)}} if theirs else None}


def judge(catalogue: Catalogue, round_: dict, guess: str) -> str | None:
    """After `guess` is added to `round_`: won, lost, or None while it goes on."""
    if _same(guess) == _same(round_["answer"]):
        return "won"
    return "lost" if len(round_["guesses"]) + 1 >= LEVELS[round_["level"]] else None


def record(rounds: list[dict], day: date) -> dict:
    """What the page says of the rounds played: the daily streak, and per level
    how many were played and won and in how many guesses.

    A day counts once it is over, or once its round is: a daily round left
    unfinished is a loss the day after, and so is a day nobody played."""
    daily = {r["day"]: r for r in rounds if r["mode"] == "daily" and r["day"]}
    won_on = {d for d, r in daily.items() if r["result"] == "won"}
    # the streak that is still alive: back from today, or from yesterday while
    # today's round has not been finished
    at = day if day.isoformat() in won_on else day - timedelta(days=1)
    streak = 0
    while at.isoformat() in won_on:
        streak, at = streak + 1, at - timedelta(days=1)
    best = run = 0
    last: date | None = None
    for iso in sorted(won_on):
        this = date.fromisoformat(iso)
        run = run + 1 if last and this - last == timedelta(days=1) else 1
        best, last = max(best, run), this
    levels = {}
    for level, tries in LEVELS.items():
        per_mode = {}
        for mode in MODES:
            # a daily round the day left behind was lost; a free one left is nothing
            over = [r for r in rounds if r["mode"] == mode and r["level"] == level
                    and (r["result"] or (mode == "daily" and r["day"] != day.isoformat()))]
            wins = [len(r["guesses"]) for r in over if r["result"] == "won"]
            per_mode[mode] = {"played": len(over), "won": len(wins),
                              "in": [wins.count(n) for n in range(1, tries + 1)]}
        levels[level] = per_mode
    return {"streak": streak, "best": max(best, streak), "levels": levels}
