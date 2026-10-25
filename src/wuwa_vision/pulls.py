# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Import a wuwatracker pull export: which resonators and weapons the user has (D53).

The user exports their pull history from wuwatracker (a JSON file of every pull:
resourceId, English name, rarity, time) and uploads it on the 更新 page. From it
only counts are kept -- copies per resonator and per weapon -- never the player
id or the pull list itself; the latest upload replaces the previous one and is
remembered until the next.

A pull is named three ways, tried in this order (D133, D135):

* by its resourceId, through the names shipped with the app (assets/
  pull_names.json) and the ones given by hand on this machine (overrides.json),
  snapped onto the catalogue's spelling;
* a resonator, by the English name the export gives it, which the wiki's own
  page for them carries as its second title ("Hsin");
* a weapon, by its English name, where somebody has named that weapon before.

Kuro's wiki has no game ids and no English names for weapons, and nothing else
is asked. So a weapon nobody has named yet stays in `unknown`, with what the
export and the id itself say about it (its English name, its rarity, its type),
until the user names it on the 更新 page -- once, for good.

Copies mean: a resonator pulled n times has 共鸣链 n - 1 (max 6); a weapon pulled
n times can be merged to 谐振 min(n, 5). 3-star and lower weapons are often fed
as EXP, so their counts are marked approximate.

Headless: the web app hands in the parsed JSON and stores what this returns.
"""

from __future__ import annotations

from collections import Counter

from .catalogue import Catalogue, plain_english

MAX_CHAIN = 6
#: The third and fourth digits of a weapon's id are its type. Not a guess: every
#: one of the 122 ids checked against its weapon's type agreed.
WEAPON_TYPE_BY_ID = {"01": "长刃", "02": "迅刀", "03": "佩枪", "04": "臂铠", "05": "音感仪"}
#: Weapons at or below this rarity are usually fed as EXP: their counts drift.
APPROX_RARITY = 3


def _match(name: str, known: set[str]) -> str | None:
    fixed = name.replace("・", "·").strip()
    if fixed in known:
        return fixed
    from .recognize.names import snap

    snapped = snap(fixed, frozenset(known))
    return snapped if snapped in known else None


_plain = plain_english


def kind_of(gid: str) -> str:
    """"weapon" or "resonator", by the id's length (8 digits against 4)."""
    return "weapon" if len(str(gid)) >= 8 else "resonator"


def describe(unknown: dict) -> dict:
    """An unplaced pull with what its id says: the kind, and a weapon's type."""
    gid = str(unknown.get("gid") or "")
    kind = kind_of(gid)
    return {**unknown, "kind": kind,
            "type": WEAPON_TYPE_BY_ID.get(gid[2:4]) if kind == "weapon" else None}


def _by_english(catalogue: Catalogue) -> dict[str, str]:
    """English name -> resonator, from the wiki's own pages (builds.json "english")."""
    people = catalogue.builds.get("resonators", {})
    named = [(_plain(b["english"]), n) for n, b in people.items() if b.get("english")]
    # a name two pages share says nothing: the eight 漂泊者 forms are all "ROVER"
    seen = Counter(english for english, _ in named)
    return {english: n for english, n in named if seen[english] == 1}


def _named_weapon(english: str, named: dict[str, str], arms: set[str]) -> str | None:
    """The weapon somebody named for this English name, in the catalogue's spelling."""
    found = named.get(_plain(english))
    return _match(found, arms) if found else None


def parse(export: dict, catalogue: Catalogue) -> dict:
    """Counts per resonator and weapon from a pull export (nothing else kept)."""
    pulls = export.get("pulls")
    if not isinstance(pulls, list):
        raise ValueError("not a wuwatracker pull export: no 'pulls' list")
    gids = catalogue.gids
    people = set(catalogue.builds.get("resonators", {}))
    arms = set(catalogue.builds.get("weapons", {})) | {
        n for n in catalogue.names() if (catalogue.entry(n) or {}).get("tab") == "武器"}
    counts = Counter(str(p.get("resourceId")) for p in pulls if isinstance(p, dict))
    names = {str(p.get("resourceId")): str(p.get("name") or "") for p in pulls
             if isinstance(p, dict)}
    stars = {str(p.get("resourceId")): p.get("qualityLevel") or p.get("rarity") for p in pulls
             if isinstance(p, dict)}
    weapon_english = catalogue.pull_english
    resonators: Counter = Counter()
    weapons: Counter = Counter()
    unknown: list[dict] = []
    english = _by_english(catalogue)
    for gid, n in counts.items():
        if gid in gids["resonators"] and (name := _match(gids["resonators"][gid], people)):
            resonators[name] += n
        elif gid in gids["weapons"] and (name := _match(gids["weapons"][gid], arms)):
            weapons[name] += n
        elif name := english.get(_plain(names.get(gid, ""))):
            resonators[name] += n
        elif name := _named_weapon(names.get(gid, ""), weapon_english, arms):
            weapons[name] += n
        else:  # an id nobody has named: say so, by the export's own name
            rarity = stars.get(gid)
            unknown.append({"gid": gid, "name": names.get(gid, ""), "copies": n,
                            **({"rarity": int(rarity)} if str(rarity or "").isdigit() else {})})
    return {"date": str(export.get("date") or "")[:32], "pulls": len(pulls),
            "resonators": dict(resonators), "weapons": dict(weapons),
            "unknown": sorted(unknown, key=lambda u: u["gid"]),
            # what the history could have listed (D179): a weapon the catalogue did not
            # know yet is newer than this import, and its absence here proves nothing
            "weapons_known": sorted(arms)}


def resolve(data: dict | None, catalogue: Catalogue) -> dict | None:
    """An import as stored, with ids that were unknown then and are named now
    (a later catalogue update, or a name set by hand) folded in."""
    if not data or not data.get("unknown"):
        return data
    gids = catalogue.gids
    people = set(catalogue.builds.get("resonators", {}))
    arms = set(catalogue.builds.get("weapons", {}))
    out = {**data, "resonators": dict(data["resonators"]), "weapons": dict(data["weapons"]),
           "unknown": []}
    english = _by_english(catalogue)
    weapon_english = catalogue.pull_english
    for u in data["unknown"]:
        gid, n = u["gid"], u["copies"]
        if gid in gids["resonators"] and (name := _match(gids["resonators"][gid], people)):
            out["resonators"][name] = out["resonators"].get(name, 0) + n
        elif gid in gids["weapons"] and (name := _match(gids["weapons"][gid], arms)):
            out["weapons"][name] = out["weapons"].get(name, 0) + n
        elif name := english.get(_plain(u.get("name") or "")):
            out["resonators"][name] = out["resonators"].get(name, 0) + n
        elif name := _named_weapon(u.get("name") or "", weapon_english, arms):
            out["weapons"][name] = out["weapons"].get(name, 0) + n
        else:
            out["unknown"].append(u)
    return out


def chain(copies: int) -> int:
    """共鸣链 from copies pulled."""
    return max(min(copies - 1, MAX_CHAIN), 0)
