# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Resonators and weapons: what building each one takes, from what is owned (D46).

Costs and profiles come from builds.json (tools/fetch_builds.py). Stock is the
merged inventory; a family's lower tiers count toward the tiers above as on the
materials page (materials.build_materials with this build as the need).

Weapons owned (copies, 谐振 rank) come from scanning the 武器 tab -- the tile
reader is not built yet, so `copies` is empty until it is (D46).

Headless: the main app renders what this returns.
"""

from __future__ import annotations

from dataclasses import asdict

from . import exp, search
from .catalogue import Catalogue
from .inventory import Item
from .materials import build_materials
from .pulls import APPROX_RARITY, chain

#: 谐振 ranks a weapon goes up to (精5 in the player's words).
MAX_RANK = 5
#: The player character's forms ("漂泊者-女-衍射"): one person, no 专武.
ROVER = "漂泊者"
#: The 漂泊者 comes in both genders and four elements, but a save file has ONE of
#: them (D72). The other gender's four forms are not "not owned yet" -- they can
#: never exist -- so they are hidden everywhere once the user says which it is,
#: and above all they stop inflating what the 材料 pages say is needed.
GENDERS = ("女", "男")


def _cost(catalogue: Catalogue, inventory: list[Item], need: dict[str, int],
          complete_tabs: set[str] | frozenset[str], exp_for: tuple | None = None) -> dict:
    """One build's materials against stock: every material with owned, short, +N;
    with `exp_for` = (kind, rarity, level from, level to), its EXP too (D52)."""
    groups = build_materials(catalogue, inventory, complete_tabs, need=need)
    rows = [{**asdict(t), "shortfall": t.shortfall}
            for g in groups for t in g.tiers if t.target > 0 or t.sent_up > 0]  # a source counts
    xp = None
    if exp_for:
        owned = {i.name: i.count or 0 for i in inventory if i.name}
        xp = exp.cost(catalogue, *exp_for, owned)
    return {
        "materials": rows,
        "shortfall": sum(r["shortfall"] for r in rows),
        "shells": need.get("贝币", 0) + (xp["shells"] if xp else 0),
        "exp": xp,
    }


def _art(catalogue: Catalogue, file: str | None) -> str | None:
    return file if file and file in catalogue.files_in("resonators") else None


def badges(catalogue: Catalogue, build: dict) -> dict:
    """A resonator's square icon and its element / weapon-type icons (D49)."""
    icons = catalogue.avatars
    return {"el_icon": icons["elements"].get(build.get("element") or ""),
            "wp_icon": icons["weapons"].get(build.get("weapon") or "")}


def resonator_summary(catalogue: Catalogue, name: str, build: dict) -> dict:
    return {
        "name": name,
        # what the name can be typed as: pinyin, initials, English (D136)
        "find": search.keys(name, catalogue.english(name) or build.get("english") or ""),
        "rarity": build.get("rarity") or 0,
        "element": build.get("element"),
        "weapon": build.get("weapon"),
        "icon": catalogue.avatar_file(name),
        **badges(catalogue, build),
        "card": _art(catalogue, build.get("card")),
        "version": build.get("version"),
        "has_costs": bool(build.get("materials")),
    }


def finished(catalogue: Catalogue, progress: dict[str, dict]) -> set[str]:
    """Resonators the user has taken all the way (D58): they want nothing more."""
    from .planner import clamp, full

    done = set()
    for name, mine in (progress or {}).items():
        if name not in catalogue.builds.get("resonators", {}):
            continue
        state = clamp(catalogue, "resonator", name, mine.get("state") or {})
        if state == full(catalogue, "resonator", name, top=True):
            done.add(name)
    return done


def remaining(catalogue: Catalogue, name: str, build: dict,
              mine: dict | None) -> dict[str, int]:
    """What is left to build (D50): from the user's saved state to the top, or the
    whole build when they set nothing."""
    if not mine:
        return build.get("materials") or {}
    from .planner import clamp, cost, full  # planner builds on this module

    top = full(catalogue, "resonator", name, top=True)
    if not (build.get("ascension") or build.get("skills")):
        # Only a total is known (a build filled in by hand, D74): there are no
        # steps to count from, so it is all of it until they are finished.
        done = clamp(catalogue, "resonator", name, mine.get("state") or {}) == top
        return {} if done else build.get("materials") or {}
    return cost(catalogue, "resonator", name, mine.get("state") or {}, top)


def _level(catalogue: Catalogue, name: str, mine: dict | None) -> int:
    """The level the user saved (1 when nothing is saved)."""
    if not mine:
        return 1
    from .planner import clamp

    return clamp(catalogue, "resonator", name, mine.get("state") or {})["level"]


def _progress_view(catalogue: Catalogue, name: str, mine: dict | None) -> dict:
    """The saved state, clamped, and whether it is the top already."""
    from .planner import clamp, full, limits

    top = full(catalogue, "resonator", name, top=True)
    base = {"limits": limits(catalogue, "resonator", name)}
    if not mine:
        return {**base, "set": False, "owned": False,
                "state": full(catalogue, "resonator", name, False), "maxed": False}
    state = clamp(catalogue, "resonator", name, mine.get("state") or {})
    return {**base, "set": True, "owned": mine.get("owned", True), "state": state,
            "maxed": state == top}


def other_gender_rovers(catalogue: Catalogue, gender: str | None) -> frozenset[str]:
    """The 漂泊者 forms this save cannot have (D72). Empty until the user says."""
    if gender not in GENDERS:
        return frozenset()
    return frozenset(
        name for name in catalogue.builds.get("resonators", {})
        if name.startswith(ROVER) and f"-{gender}-" not in name
    )


def is_rover(name: str) -> bool:
    return name.startswith(ROVER)


def shared_rover(catalogue: Catalogue, progress: dict[str, dict] | None,
                 skip: frozenset[str] | set[str] = frozenset()) -> dict[str, dict]:
    """`progress` with the 漂泊者's level and ascension on every one of its forms (D118).

    The 漂泊者 is one character who changes element. Level and ascension are paid
    once -- the 神秘密码, the 金阳凤, the EXP -- and every form has them; only the
    skills are each form's own. Counted per form, a second element asks for a
    whole ascension again, and for 神秘密码 that nothing in the game can supply.
    A form nobody saved gets the shared level and its skills at the start.
    """
    progress = progress or {}
    forms = [n for n in catalogue.builds.get("resonators", {}) if is_rover(n) and n not in skip]
    states = [progress[n].get("state") or {} for n in forms if n in progress]
    if not states:
        return progress

    def top(key: str, low: int) -> int:
        return max(int(s.get(key) or low) for s in states)

    level, ascension = top("level", 1), top("ascension", 0)
    out = dict(progress)
    for name in forms:
        mine = out.get(name) or {"owned": True, "chain": None}
        out[name] = {**mine, "state": {**(mine.get("state") or {}),
                                       "level": level, "ascension": ascension}}
    return out


def _has(name: str, mine: dict | None, copies: int) -> bool:
    """On the account: the story's 漂泊者, a pull, or the user's own word."""
    return (is_rover(name) or bool(mine and mine.get("owned")) or copies > 0
            or (mine or {}).get("chain") is not None)


def on_account(catalogue: Catalogue, progress: dict[str, dict] | None,
               pulls: dict | None = None,
               skip: frozenset[str] | set[str] = frozenset()) -> set[str]:
    """The resonators the user has: pulled, marked by hand, or the 漂泊者 (D116)."""
    progress = progress or {}
    pulled = (pulls or {}).get("resonators") or {}
    return {name for name in catalogue.builds.get("resonators", {})
            if name not in skip and _has(name, progress.get(name), pulled.get(name, 0))}


def needed_by(catalogue: Catalogue, progress: dict[str, dict] | None,
              pulls: dict | None = None,
              skip: frozenset[str] | set[str] = frozenset()) -> dict[str, tuple[str, int]]:
    """Per material: who, of the resonators the user has, still needs the most of
    it, and how much (D117, D122).

    Someone finished wants nothing; someone not on the account wants nothing
    yet. What is left for the rest is counted from where each stands.
    """
    progress = progress or {}
    pulled = (pulls or {}).get("resonators") or {}
    out: dict[str, tuple[str, int]] = {}
    for name, build in catalogue.builds.get("resonators", {}).items():
        if name in skip or not build.get("materials"):
            continue
        mine = progress.get(name)
        if not _has(name, mine, pulled.get(name, 0)):
            continue
        for material, n in remaining(catalogue, name, build, mine).items():
            if n > out.get(material, ("", 0))[1]:
                out[material] = (name, n)
    return out


def still_needed(catalogue: Catalogue, progress: dict[str, dict] | None,
                 pulls: dict | None = None,
                 skip: frozenset[str] | set[str] = frozenset()) -> dict[str, int]:
    """Per material: the most any ONE resonator the user has still needs (D117)."""
    return {material: n for material, (_, n) in
            needed_by(catalogue, progress, pulls, skip).items()}


def resonators(catalogue: Catalogue, inventory: list[Item] | None = None,
               complete_tabs: set[str] | frozenset[str] = frozenset(),
               progress: dict[str, dict] | None = None,
               pulls: dict | None = None,
               skip: frozenset[str] | set[str] = frozenset()) -> list[dict]:
    """Every resonator, for the list; with `inventory`, how short what is left of
    its build is (the whole build unless the user saved where it stands)."""
    progress = progress or {}
    out = []
    for name, build in catalogue.builds.get("resonators", {}).items():
        if name in skip:
            continue
        row = resonator_summary(catalogue, name, build)
        mine = progress.get(name)
        copies = ((pulls or {}).get("resonators") or {}).get(name, 0)
        by_hand = (mine or {}).get("chain")
        row["owned"] = bool(mine and mine.get("owned")) or copies > 0 or by_hand is not None
        row["copies"] = copies
        # A pull export cannot see a free copy or a top-up pack, so a chain set
        # by hand wins over the one the pulls imply (D69).
        row["chain"] = by_hand if by_hand is not None else (chain(copies) if copies else None)
        row["chain_by_hand"] = by_hand is not None
        if is_rover(name):
            # The story hands these out; there is no 共鸣链 to track (D72).
            row["chain"], row["chain_by_hand"], row["owned"] = None, False, True
        if inventory is not None and build.get("materials"):
            need = remaining(catalogue, name, build, mine)
            row["maxed"] = bool(mine) and not need
            row["shortfall"] = _cost(catalogue, inventory, need, complete_tabs)["shortfall"]
        out.append(row)
    return out


def signature_dishes(catalogue: Catalogue) -> dict[str, list[dict]]:
    """resonator -> the dishes only they cook ("使用X烹饪Y有概率获得"), with the base dish."""
    from .cooking import _SIGNATURE

    out: dict[str, list[dict]] = {}
    for item in catalogue.craftables():
        hit = _SIGNATURE.search(item.get("获取途径") or "")
        if hit:
            base = catalogue.named(hit.group(2))
            out.setdefault(hit.group(1).strip(), []).append(
                {"name": item["name"], "base": base})
    return out


def dish_variants(catalogue: Catalogue) -> list[tuple[str, str]]:
    """(dish, its special version): drawn alike, told apart by colour in a scan (D193)."""
    return [(dish["base"], dish["name"]) for dishes in signature_dishes(catalogue).values()
            for dish in dishes if dish.get("base")]


def resonator(catalogue: Catalogue, inventory: list[Item], name: str,
              complete_tabs: set[str] | frozenset[str] = frozenset(),
              mine: dict | None = None, pulls: dict | None = None) -> dict | None:
    build = catalogue.builds.get("resonators", {}).get(name)
    if build is None:
        return None
    owned = {i.name: i.count or 0 for i in inventory if i.name}
    dishes = signature_dishes(catalogue).get(name, [])
    if build.get("dish") and not any(d["name"] == build["dish"] for d in dishes):
        dishes.insert(0, {"name": build["dish"], "base": None})
    return {
        **resonator_summary(catalogue, name, build),
        "portrait": _art(catalogue, build.get("portrait")),
        "gender": build.get("gender"),
        "birthplace": build.get("birthplace"),
        "faction": build.get("faction"),
        "description": build.get("description"),
        "dishes": [{**d, "owned": owned.get(d["name"], 0),
                    "icon_file": catalogue.icon_file(d["name"]),
                    "rarity": (catalogue.entry(d["name"]) or {}).get("rarity") or 0}
                   for d in dishes],
        "cost": _cost(catalogue, inventory, remaining(catalogue, name, build, mine),
                      complete_tabs, exp_for=("resonator", build.get("rarity") or 5,
                                              _level(catalogue, name, mine), exp.CAPS[-1])),
        "progress": _progress_view(catalogue, name, mine),
        "copies": ((pulls or {}).get("resonators") or {}).get(name, 0),
        "chain": None if is_rover(name) else (
            (mine or {}).get("chain") if (mine or {}).get("chain") is not None
            else chain(((pulls or {}).get("resonators") or {}).get(name, 0))),
        "chain_by_hand": not is_rover(name) and (mine or {}).get("chain") is not None,
        "rover": is_rover(name),
        "signature": signatures(catalogue).get(name),
        "weapons": sorted(
            ({**weapon_summary(catalogue, n, w, ((pulls or {}).get("weapons") or {}).get(n, 0)),
              "signature": signatures(catalogue).get(name) == n}
             for n, w in catalogue.builds.get("weapons", {}).items()
             if w.get("type") and w.get("type") == build.get("weapon")),
            key=lambda w: (not w["signature"], -w["rarity"], w["name"])),
        "signature_choices": sorted(
            n for n, w in catalogue.builds.get("weapons", {}).items()
            if w.get("type") == build.get("weapon") and (w.get("rarity") or 0) == 5
            and is_limited(w)),
    }


def _version(v: str | None) -> tuple[int, ...]:
    return tuple(int(x) for x in (v or "").lstrip("Vv").split(".") if x.isdigit())


def is_limited(build: dict) -> bool:
    """A limited-banner weapon: 获取途径 "武器活动唤取" / "唤取", never "常驻"."""
    source = build.get("source") or ""
    return "唤取" in source and "常驻" not in source


def signatures(catalogue: Catalogue) -> dict[str, str]:
    """resonator -> its 专武, derived (the wiki has no such field; D46).

    A 专武 is a limited 5-star weapon of the resonator's weapon type, released in
    the same version. When one version brought two such resonators or weapons,
    the resonator's 武器推荐 first pick decides; otherwise none is claimed rather
    than a wrong one. Standard (常驻) weapons are never anyone's 专武.
    """
    cached = catalogue.__dict__.get("_signatures")
    if cached is not None:
        return cached
    people = catalogue.builds.get("resonators", {})
    arms = {n: w for n, w in catalogue.builds.get("weapons", {}).items()
            if (w.get("rarity") or 0) == 5 and is_limited(w) and w.get("version")}
    out: dict[str, str] = {}
    for name, weapon_build in arms.items():
        owners = [r for r, b in people.items()
                  if not r.startswith(ROVER)  # the 漂泊者 forms have no 专武
                  and (b.get("rarity") or 0) == 5 and b.get("weapon") == weapon_build.get("type")
                  and _version(b.get("version")) == _version(weapon_build.get("version"))]
        if len(owners) > 1:
            owners = [r for r in owners if (people[r].get("recommended") or [None])[0] == name]
        if len(owners) == 1 and owners[0] not in out:
            out[owners[0]] = name
    # Set by hand in the resonator panel: wins; "" means "has none".
    for who, name in catalogue.overrides["signatures"].items():
        out = {r: w for r, w in out.items() if w != name or r == who}
        if name:
            out[who] = name
        else:
            out.pop(who, None)
    catalogue.__dict__["_signatures"] = out
    return out


def weapon_summary(catalogue: Catalogue, name: str, build: dict, copies: int = 0) -> dict:
    """A weapon for lists; `copies` from the imported pulls (D53), each at rank 1
    until the weapons-tab scan reads real ranks."""
    entry = catalogue.entry(name) or {}
    rarity = build.get("rarity") or entry.get("rarity") or 0
    return {
        "name": name,
        "find": search.keys(name, catalogue.english(name) or ""),
        "type": build.get("type"),
        "type_icon": catalogue.avatars["weapons"].get(build.get("type") or ""),
        "rarity": rarity,
        "icon_file": catalogue.icon_file(name),
        "copies": [1] * copies,
        "rank_reachable": reachable_rank([1] * copies) if copies else None,
        # 3-star and lower are often fed as EXP: pulled is not what is left
        "approx": bool(copies) and rarity <= APPROX_RARITY,
    }


def reachable_rank(ranks: list[int]) -> int:
    """The 谐振 rank all copies merged into one reach: each copy at rank r carries r
    (itself plus the r-1 merged into it before). Capped at MAX_RANK."""
    return min(sum(max(r, 1) for r in ranks), MAX_RANK) if ranks else 0


def weapons(catalogue: Catalogue, pulls: dict | None = None) -> list[dict]:
    have = (pulls or {}).get("weapons") or {}
    return [weapon_summary(catalogue, n, w, have.get(n, 0))
            for n, w in catalogue.builds.get("weapons", {}).items()]


def weapon(catalogue: Catalogue, inventory: list[Item], name: str,
           complete_tabs: set[str] | frozenset[str] = frozenset(),
           pulls: dict | None = None,
           skip: frozenset[str] | set[str] = frozenset()) -> dict | None:
    """One weapon, with who can use it. `skip`: the 漂泊者 forms this save cannot
    have (D72) -- an account has one gender, and the other's forms are nobody (D146)."""
    build = catalogue.builds.get("weapons", {}).get(name)
    if build is None:
        return None
    owner = next((r for r, w in signatures(catalogue).items() if w == name), None)
    people = catalogue.builds.get("resonators", {})
    users = [avatar(catalogue, n, r) for n, r in people.items()
             if r.get("weapon") and r.get("weapon") == build.get("type") and n not in skip]
    users.sort(key=lambda u: (u["name"] != owner, -u["rarity"], u["name"]))
    return {
        **weapon_summary(catalogue, name, build, ((pulls or {}).get("weapons") or {}).get(name, 0)),
        "cost": _cost(catalogue, inventory, build.get("materials") or {}, complete_tabs,
                      exp_for=("weapon", build.get("rarity") or 5, 1, exp.CAPS[-1])),
        "wielders": users,
        "signature_of": owner,
        "limited": is_limited(build),
        "version": build.get("version"),
    }


def avatar(catalogue: Catalogue, name: str, build: dict,
           faces: dict[str, str] | None = None) -> dict:
    """A resonator as an icon: name, rarity and card art (the page crops it).

    `faces` maps a resonator to the portrait a 武器 tile wore (D61). It is the
    game's own head icon, and for someone too new for wuwatracker it is the only
    real one there is -- better than a crop of the card art (D82).
    """
    return {"name": name, "rarity": build.get("rarity") or 0,
            "find": search.keys(name, catalogue.english(name) or build.get("english") or ""),
            "card": _art(catalogue, build.get("card")), "icon": catalogue.avatar_file(name),
            "face": (faces or {}).get(name),
            "element": build.get("element"), "weapon": build.get("weapon"),
            **badges(catalogue, build)}

