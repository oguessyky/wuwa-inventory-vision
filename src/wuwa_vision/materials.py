# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""The material stock view (D45 decision 9, phase 3).

Target per material = what ONE full build needs of it: a resonator to level 90
with every skill maxed, plus a weapon to level 90 -- the most any resonator needs
of it plus the most any weapon needs of it, so the stock covers whichever build
comes next. Costs come from builds.json (tools/fetch_builds.py).

Materials combine upward (合成-纯化): enemy drops (低频 -> 中频 -> 高频 -> 全频) and
each weapon type's materials form families of four tiers, and a surplus at a lower
tier covers a shortfall above it at SYNTHESIS_RATIO : 1. Families are read from
the builds themselves -- within one build, the enemy drops are one family and the
weapon-type materials another -- because names alone do not show them
(声律种核 -> 声律萌芽 -> 声律新叶 -> 声律花蕾).

Headless: the main app renders what this returns.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass, field

from .catalogue import Catalogue
from .inventory import Item

#: Lower-tier units per higher-tier unit in 合成-纯化. The wiki pages do not state
#: it; 3 : 1 is the game's purification ratio. One constant, easy to correct.
SYNTHESIS_RATIO = 3
#: Not bag items: the currency is shown in the game's header, not in 资源/素材.
CURRENCY = {"贝币"}
#: 功能 of an enemy drop (all four tiers read the same).
ENEMY = "用于武器突破、共鸣者突破与技能升级"
#: 功能 of a weapon-type material: "用于使用长刃的角色的武器突破与技能升级的初级材料".
WEAPON_KIND = "的角色的武器突破与技能升级"
#: 类型 of the standalone materials -> what the pages call them.
ROLES = {"技能升级材料": "周本", "共鸣者突破材料": "BOSS", "突破材料": "特产"}
_DROP = re.compile(r"^(.+?)的?掉落物")
#: How the wiki says a thing is picked up off the ground.
GATHERED = "采集"
#: 功能 of a thing a resonator ascends with and nothing else.
ASCENDS = "用于共鸣者突破"


def role_of(catalogue: Catalogue, name: str) -> tuple[str | None, str | None]:
    """(周本 | BOSS | 特产 | None, the enemy that drops it or None).

    The wiki's 类型 is taken at its word, with one correction (D143): it files the
    flower “来生” with the boss drops. Nothing drops it and it is gathered, so it
    is a 特产 -- and whatever the wiki files that way next is read the same.
    长离's 雀翎果 it files as plain “素材” (D147): gathered, and for ascending a
    resonator, so that is a 特产 too.
    """
    page = catalogue.page(name)
    use = (page.get("功能") or "").strip()
    drop = _DROP.match(use)
    role = ROLES.get((page.get("类型") or "").strip())
    unfiled = role is None and use.startswith(ASCENDS)
    if (role == "BOSS" or unfiled) and not drop and GATHERED in (page.get("获取途径") or ""):
        role = "特产"
    return role, drop.group(1) if drop else None


def rover_only(catalogue: Catalogue) -> frozenset[str]:
    """Materials no build but the 漂泊者's own asks for (神秘密码): nothing to offer
    when somebody else's build is being filled in (D143)."""
    from .roster import is_rover  # roster builds on this module

    users: dict[str, list[str]] = {}
    for kind in ("resonators", "weapons"):
        for who, build in catalogue.builds.get(kind, {}).items():
            for material in build.get("materials") or {}:
                users.setdefault(material, []).append(who if kind == "resonators" else "")
    return frozenset(m for m, who in users.items() if all(is_rover(w) for w in who))


@dataclass
class Stock:
    name: str
    rarity: int
    owned: int
    target: int
    from_below: int = 0
    """Units of this tier to synthesise from the tier below -- only what is needed:
    this tier's own shortfall plus what the tier above takes from it (D51)."""
    sent_up: int = 0
    """Units of this tier used up to synthesise the tier above (SYNTHESIS_RATIO each)."""
    to_name: str | None = None
    kept: int = 0
    """Of `from_below`, what this tier keeps for its own shortfall (the rest passes
    up): the "+N" on its tile."""
    sources: list = field(default_factory=list)
    """Which lower tiers were used up to make `kept`, lowest first: [{name, rarity,
    icon_file, used}] -- the hover shows only these (D51)."""
    family: str | None = None
    """The family's top tier: the tiles of one family share it (hover plan)."""
    icon_file: str | None = None
    known: bool = False
    from_name: str | None = None
    """The tier below that `from_below` comes from, with its rarity and icon."""
    from_rarity: int = 0
    from_icon: str | None = None
    by_hand: bool = False
    """The target is the user's own, not what the builds ask for (D84)."""
    base: int = 0
    """The least to keep, the user's own floor under the target (D158); 0: none."""
    per_build: dict = field(default_factory=dict)
    """{"resonator": n, "weapon": n} -- what ONE full build of each costs (D86),
    the unit to stock up in for a character who is not out yet."""
    role: str | None = None
    """周本 (weekly boss), BOSS (overworld boss), 特产 (gathered) -- from 类型."""
    drop: str | None = None
    """Who drops it ("哀声鸷"), from 功能 "X的掉落物"."""
    drop_icon: str | None = None
    """That boss's portrait (tools/fetch_bosses.py), shown instead of its name."""

    @property
    def shortfall(self) -> int:
        return max(self.target + self.sent_up - self.owned - self.from_below, 0)


def plan_synthesis(tiers: list[Stock]) -> None:
    """Fill each tier's `from_below` / `sent_up`, lowest tier first in `tiers` (D51).

    Bottom-up, what each tier COULD receive: the tier below's surplus over its own
    target (after what it received itself), divided by the ratio. Top-down, what
    is actually made: the top tier takes what it lacks, up to what it could get;
    the tier below must then cover its own target plus RATIO x that, and so on.
    Every tier keeps its own target first; nothing is converted that no tier
    needs, so a tier that is already full shows no "+N".
    """
    could = [0] * len(tiers)
    for i in range(1, len(tiers)):
        below = tiers[i - 1]
        spare = below.owned + could[i - 1] - below.target
        could[i] = spare // SYNTHESIS_RATIO if spare > 0 else 0
    above_takes = 0
    for i in range(len(tiers) - 1, -1, -1):
        tier = tiers[i]
        tier.sent_up = above_takes * SYNTHESIS_RATIO if i < len(tiers) - 1 else 0
        want = max(tier.target + tier.sent_up - tier.owned, 0)
        tier.from_below = min(want, could[i])
        above_takes = tier.from_below
        tier.family = tiers[-1].name
        if i + 1 < len(tiers):
            tier.to_name = tiers[i + 1].name
        if i > 0:
            below = tiers[i - 1]
            tier.from_name, tier.from_rarity, tier.from_icon = (
                below.name, below.rarity, below.icon_file)
    _attribute(tiers)


def _attribute(tiers: list[Stock]) -> None:
    """Per tier: what it keeps, and which lower units made exactly that.

    A lower tier spends its own spare (over its target) first, then units it made
    itself from further down; lower tiers' needs are served first. Summed over the
    tiers above, each tier's `used` equals its `sent_up`.
    """
    spare = [max(t.owned - t.target, 0) for t in tiers]
    for h, tier in enumerate(tiers):
        tier.kept = min(tier.from_below, max(tier.target - tier.owned, 0))
        tier.sources = []
        need, i = tier.kept * SYNTHESIS_RATIO, h - 1
        while need > 0 and i >= 0:
            own = min(need, spare[i])
            spare[i] -= own
            # used: all units of tier i consumed; own: what leaves its own pile (the
            # rest was made from further down and only passes through it)
            tier.sources.insert(0, {"name": tiers[i].name, "rarity": tiers[i].rarity,
                                    "icon_file": tiers[i].icon_file, "used": need,
                                    "own": own})
            need = (need - own) * SYNTHESIS_RATIO
            i -= 1


@dataclass
class Group:
    """One family (tiers combine upward) or one standalone material."""

    key: str
    kind: str
    """enemy | weapon | other -- what the page groups by."""
    label: str
    tiers: list[Stock] = field(default_factory=list)

    @property
    def shortfall(self) -> int:
        return sum(t.shortfall for t in self.tiers)

    def as_dict(self) -> dict:
        return {
            "key": self.key, "kind": self.kind, "label": self.label, "shortfall": self.shortfall,
            "tiers": [{**asdict(t), "shortfall": t.shortfall} for t in self.tiers],
        }


def per_build(catalogue: Catalogue,
              skip: set[str] | frozenset[str] = frozenset()) -> dict[str, dict[str, int]]:
    """Per material: the most ONE resonator needs, and the most ONE weapon needs.

    The unit the page already counts in, pulled out so it can be offered as a
    button (D86). Deliberately ignores `done`: stocking up is about a character
    who does not exist yet, and a finished resonator is still evidence of what a
    full build of one costs.
    """
    out: dict[str, dict[str, int]] = {}
    for kind, one in (("resonators", "resonator"), ("weapons", "weapon")):
        for who, build in catalogue.builds.get(kind, {}).items():
            if who in skip:
                continue
            for name, n in (build.get("materials") or {}).items():
                if name in CURRENCY:
                    continue
                row = out.setdefault(name, {"resonator": 0, "weapon": 0})
                row[one] = max(row[one], n)
    return out


#: The kinds every build draws on: stocked for one full build of anyone (D117).
FAMILY_SLOTS = ("enemy", "weapon")


def targets(catalogue: Catalogue, done: set[str] | frozenset[str] = frozenset(),
            extra: dict[str, int] | None = None,
            skip: set[str] | frozenset[str] = frozenset(),
            wanted: dict[str, int] | None = None,
            still: dict[str, int] | None = None,
            base: dict[str, int] | None = None) -> dict[str, int]:
    """Per material: the most any resonator needs + the most any weapon needs.

    `base` (D158) is a floor under all of it, a hand-set target included: the
    least the user wants to keep of something a shop sells. It is another number
    than the target, and never lowers one.

    `still` (D117) narrows that for the materials only some builds use -- a boss
    drop, a weekly drop, a 特产, the 漂泊者's 神秘密码. Enemy drops and weapon
    material are worth stocking for whoever comes next; a boss drop is worth
    nothing until someone the user has wants it. So for those, the target is
    what `still` says someone still needs (`roster.still_needed`), and nothing
    when nobody does -- 46 of a boss drop nobody on the account uses is not a
    shortage. The user's own target (`wanted`) still overrides either way.

    `done` -- resonators the user has finished (D58) -- create no demand any more:
    a material only they use ends at target 0, and its tiles then show the plain
    count. `extra` adds what something else still needs of it (dishes below their
    target keep a 特产 wanted). `skip` is for builds this save cannot have at all
    -- the other gender's 漂泊者 forms (D72) -- which are left out entirely.

    `wanted` is a target the user set by hand on the 材料 page (D84) and it
    REPLACES the computed one, in both directions: stock 600 of something for a
    character who is not out yet, or stop tracking one at 0.
    """
    builds = catalogue.builds
    most: dict[str, int] = {}
    peaks: dict[str, dict[str, int]] = {}
    for kind in ("resonators", "weapons"):
        peak = peaks[kind] = {}
        for who, build in builds.get(kind, {}).items():
            if who in skip:
                continue
            if kind == "resonators" and who in done:
                # still a build material, just not wanted any more: target 0
                for name in build.get("materials") or {}:
                    if name not in CURRENCY:
                        most.setdefault(name, 0)
                continue
            for name, n in (build.get("materials") or {}).items():
                if name not in CURRENCY:
                    peak[name] = max(peak.get(name, 0), n)
        for name, n in peak.items():
            most[name] = most.get(name, 0) + n
    if still is not None:
        for name in most:
            if slot_of(catalogue, name) not in FAMILY_SLOTS:
                most[name] = still.get(name, 0) + peaks["weapons"].get(name, 0)
    for name, n in (extra or {}).items():
        most[name] = max(most.get(name, 0), n)
    for name, n in (wanted or {}).items():
        most[name] = n
    for name, n in (base or {}).items():
        most[name] = max(most.get(name, 0), n)
    return most


def reasons(catalogue: Catalogue, name: str,
            done: set[str] | frozenset[str] = frozenset(),
            skip: set[str] | frozenset[str] = frozenset(),
            wanted: dict[str, int] | None = None,
            needed: dict[str, tuple[str, int]] | None = None,
            dishes: list[dict] | None = None,
            base: dict[str, int] | None = None) -> dict:
    """Where `name`'s target comes from (D122): the same sum `targets` does, itemised.

    A number on a tile that nobody can account for is not information. This
    names what is behind it: the resonator who still needs the most of it (or,
    for a family, whose full build takes the most), the weapon that takes the
    most, and the dishes below their target that eat it. `by` says which of
    them the target is: "hand" (the user set it), "dishes" (cooking wants more
    than the builds do), or "builds" -- or "base" (D158), when the least the user
    wants to keep is more than any of them. `under` is then what it stands over.
    """
    said = _reasons(catalogue, name, done, skip, wanted, needed, dishes)
    floor = (base or {}).get(name, 0)
    if floor > said["total"]:
        return {**said, "by": "base", "under": said["by"], "total": floor, "base": floor}
    return {**said, "base": floor}


def _reasons(catalogue: Catalogue, name: str, done: set[str] | frozenset[str],
             skip: set[str] | frozenset[str], wanted: dict[str, int] | None,
             needed: dict[str, tuple[str, int]] | None, dishes: list[dict] | None) -> dict:
    if wanted and name in wanted:
        return {"by": "hand", "builds": [], "dishes": dishes or [], "total": wanted[name]}
    family = slot_of(catalogue, name) in FAMILY_SLOTS
    parts: list[dict] = []
    for kind, one in (("resonators", "resonator"), ("weapons", "weapon")):
        best: tuple[str, int] = ("", 0)
        if one == "resonator" and needed is not None and not family:
            best = needed.get(name, best)
        else:
            for who, build in catalogue.builds.get(kind, {}).items():
                if who in skip or (one == "resonator" and who in done):
                    continue
                n = (build.get("materials") or {}).get(name, 0)
                if n > best[1]:
                    best = (who, n)
        if best[1]:
            # a family is stocked for a whole build; the rest for what is left
            parts.append({"kind": one, "name": best[0], "amount": best[1],
                          "full": one == "weapon" or family or needed is None})
    built = sum(part["amount"] for part in parts)
    cooked = sum(d["amount"] for d in dishes or [])
    return {"by": "dishes" if cooked > built else "builds" if built else None,
            "builds": parts, "dishes": dishes or [], "total": max(built, cooked)}


def users(catalogue: Catalogue, name: str,
          done: set[str] | frozenset[str] = frozenset(),
          skip: set[str] | frozenset[str] = frozenset(),
          progress: dict[str, dict] | None = None) -> dict[str, list[dict]]:
    """Which resonators and weapons need `name`, as icons for the detail panel.

    With `progress`, "need" means what is LEFT of this material for each of them
    (D83). 莫特斐 at level 90 with skills at 6 is not finished, so D58 did not
    mark them -- but they want none of 怒号声核 any more, and the panel said they
    did. `left` is that number; `maxed` is "wants none of this one", which is
    what the veil in the panel actually means.
    """
    from .roster import remaining  # roster builds on this module
    folder = catalogue.directory / "resonators"
    out: dict[str, list[dict]] = {}
    for kind in ("resonators", "weapons"):
        who = []
        for build_name, build in sorted(catalogue.builds.get(kind, {}).items()):
            if name not in (build.get("materials") or {}) or build_name in skip:
                continue
            want = (build.get("materials") or {}).get(name, 0)
            left = want
            if kind == "resonators" and progress is not None:
                left = remaining(catalogue, build_name, build,
                                 (progress or {}).get(build_name)).get(name, 0)
            row = {"name": build_name, "rarity": build.get("rarity") or 0,
                   "needs": want, "left": left,
                   "maxed": kind == "resonators" and (build_name in done or not left)}
            if kind == "resonators":
                card = build.get("card")
                row["card"] = card if card and card in catalogue.files_in(folder.name) else None
                row["icon"] = catalogue.avatar_file(build_name)
                row["element"], row["weapon"] = build.get("element"), build.get("weapon")
                row["el_icon"] = catalogue.avatars["elements"].get(row["element"] or "")
                row["wp_icon"] = catalogue.avatars["weapons"].get(row["weapon"] or "")
            else:
                row["icon_file"] = catalogue.icon_file(build_name)
            who.append(row)
        if who:
            # the ones who still want it first; the rest go quiet at the end
            out[kind] = sorted(who, key=lambda r: (r["maxed"], -r["rarity"], r["name"]))
    return out


def _kind(catalogue: Catalogue, name: str) -> str:
    use = catalogue.page(name).get("功能") or ""
    if use.startswith(ENEMY):
        return "enemy"
    return "weapon" if WEAPON_KIND in use else "other"


#: 周本 / BOSS / 特产 as the hand-edit form names its boxes (D115).
_SLOT_OF_ROLE = {"周本": "weekly", "BOSS": "boss", "特产": "flower"}


def slot_of(catalogue: Catalogue, name: str) -> str:
    """Which box of a build `name` belongs in (D115): coin, enemy, weapon, boss,
    weekly, flower -- or other, for what the game has no fixed place for."""
    if name in CURRENCY:
        return "coin"
    kind = _kind(catalogue, name)
    if kind != "other":
        return kind
    return _SLOT_OF_ROLE.get(role_of(catalogue, name)[0] or "", "other")


def typical(catalogue: Catalogue, kind: str) -> dict[int, dict[str, list[int]]]:
    """rarity -> slot -> the amounts most builds of that rarity take, lowest tier
    first (D115).

    Every 5-star resonator costs the same; so the form can offer the numbers and
    leave only the choice of material. Read off the builds the catalogue has, so
    a patch that changes the cost changes this with it.
    """
    votes: dict[int, dict[str, Counter[tuple[int, ...]]]] = {}
    for build in catalogue.builds.get(kind, {}).values():
        by_slot: dict[str, list[tuple[int, int]]] = {}
        for name, amount in (build.get("materials") or {}).items():
            tier = (catalogue.entry(name) or {}).get("rarity") or 0
            by_slot.setdefault(slot_of(catalogue, name), []).append((tier, amount))
        for slot, pairs in by_slot.items():
            amounts = tuple(amount for _, amount in sorted(pairs))
            votes.setdefault(build.get("rarity") or 0, {}).setdefault(slot, Counter())[amounts] += 1
    return {rarity: {slot: list(seen.most_common(1)[0][0]) for slot, seen in slots.items()}
            for rarity, slots in votes.items()}


#: The stock-up sets the 材料 panel offers (D88), in the order it shows them:
#: which kinds of ONE full build each one adds up.
PRESETS: dict[str, tuple[str, ...]] = {
    "both": ("resonator", "weapon"),
    "resonator": ("resonator",),
    "weapon": ("weapon",),
}


def family(catalogue: Catalogue, name: str) -> list[str]:
    """The tiers `name` combines with, lowest first -- or just itself (D88)."""
    return next((chain for chain in families(catalogue) if name in chain), [name])


def preset(catalogue: Catalogue, name: str, which: str,
           skip: set[str] | frozenset[str] = frozenset()) -> dict[str, int]:
    """Targets for `name`'s whole family, enough for one `which` (D88).

    A set, not one material: stocking for a character who is not out yet means
    every tier they will eat, and they eat all four. Each tier gets what ONE
    resonator and/or ONE weapon needs of it at most (`per_build`).
    """
    one = per_build(catalogue, skip)
    return {n: sum((one.get(n) or {}).get(k, 0) for k in PRESETS[which])
            for n in family(catalogue, name)}


def families(catalogue: Catalogue) -> list[list[str]]:
    """Tier chains, lowest first: the same kind of material inside one build.

    Worked out once per loaded catalogue (a reload is a new Catalogue)."""
    cached = catalogue.__dict__.get("_families")
    if cached is None:
        cached = catalogue.__dict__["_families"] = _families(catalogue)
    return [list(c) for c in cached]


def _families(catalogue: Catalogue) -> list[list[str]]:
    parent: dict[str, str] = {}

    def root(x: str) -> str:
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for kind in ("resonators", "weapons"):
        for build in catalogue.builds.get(kind, {}).values():
            by_kind: dict[str, list[str]] = {}
            for name in build.get("materials") or {}:
                k = _kind(catalogue, name)
                if k != "other":
                    by_kind.setdefault(k, []).append(name)
            for names in by_kind.values():
                # A build drawing on two families of one kind (丽贝卡, 漂泊者) shows
                # two items per tier: it cannot tell which belong together.
                tiers = [(catalogue.entry(n) or {}).get("rarity") for n in names]
                if len(set(tiers)) != len(tiers):
                    continue
                for other in names[1:]:
                    parent[root(other)] = root(names[0])
    chains: dict[str, list[str]] = {}
    for name in parent:
        chains.setdefault(root(name), []).append(name)
    rarity = lambda n: (catalogue.entry(n) or {}).get("rarity") or 0  # noqa: E731
    derived = [sorted(c, key=rarity) for c in chains.values() if len(c) > 1]
    # Tiers no single-family build ties together (D124): the four 面罩 are only
    # ever used beside another family, which is exactly the case skipped above.
    # What is left of one kind, ending in the same two characters and one to a
    # tier, is a family by the game's own naming.
    tied = {n for c in derived for n in c}
    loose: dict[tuple[str, str], list[str]] = {}
    for name in catalogue.names():
        kind = _kind(catalogue, name)
        if kind != "other" and name not in tied:
            loose.setdefault((kind, name[-2:]), []).append(name)
    for names in loose.values():
        tiers = [rarity(n) for n in names]
        if len(names) > 1 and len(set(tiers)) == len(tiers):
            derived.append(sorted(names, key=rarity))
    # Families set by hand (更新 page, D46) win: their members leave any derived
    # chain, and they keep the order they were given in (lowest tier first).
    manual = [list(f) for f in catalogue.overrides["families"] if len(f) > 1]
    taken = {n for f in manual for n in f}
    derived = [[n for n in c if n not in taken] for c in derived]
    return [c for c in derived if len(c) > 1] + manual


def build_materials(catalogue: Catalogue, inventory: list[Item],
                    complete_tabs: set[str] | frozenset[str] = frozenset(),
                    need: dict[str, int] | None = None,
                    done: set[str] | frozenset[str] = frozenset(),
                    extra: dict[str, int] | None = None,
                    skip: set[str] | frozenset[str] = frozenset(),
                    wanted: dict[str, int] | None = None,
                    still: dict[str, int] | None = None,
                    base: dict[str, int] | None = None) -> list[Group]:
    """Stock against `need` (default: one full build of anything, `targets`).

    Pass one resonator's or weapon's own costs as `need` to see what building
    exactly that one takes; only the families it uses are returned then.
    """
    whole = need is None
    by_hand = set(wanted or ()) if whole else set()
    one_of_each = per_build(catalogue, skip)
    floors = (base or {}) if whole else {}
    need = targets(catalogue, done, extra, skip, wanted, still, base) if need is None else {
        n: k for n, k in need.items() if n not in CURRENCY}
    owned = {i.name: i for i in inventory if i.name}

    def stock(name: str) -> Stock:
        entry = catalogue.entry(name) or {}
        mine = owned.get(name)
        role, drop = role_of(catalogue, name)
        return Stock(
            name=name, rarity=int(entry.get("rarity") or 0),
            owned=(mine.count or 0) if mine else 0, target=need.get(name, 0),
            icon_file=catalogue.icon_file(name),
            known=mine is not None or entry.get("tab") in complete_tabs,
            by_hand=name in by_hand, base=floors.get(name, 0),
            per_build=one_of_each.get(name, {"resonator": 0, "weapon": 0}),
            role=role, drop=drop, drop_icon=catalogue.bosses.get(drop or ""),
        )

    groups: list[Group] = []
    placed: set[str] = set()
    for chain in families(catalogue):
        if not whole and not any(n in need for n in chain):
            continue
        tiers = [stock(n) for n in chain]
        plan_synthesis(tiers)
        kind = _kind(catalogue, chain[0])
        use = catalogue.page(chain[0]).get("功能") or ""
        weapon = kind == "weapon" and "使用" in use
        label = use.split("使用")[1].split("的角色")[0] if weapon else ""
        groups.append(Group(key=chain[-1], kind=kind, label=label, tiers=tiers))
        placed.update(chain)
    for name in sorted(need):
        if name not in placed:
            page = catalogue.page(name)
            groups.append(Group(key=name, kind="other", label=page.get("类型") or "",
                                tiers=[stock(name)]))
    return groups
