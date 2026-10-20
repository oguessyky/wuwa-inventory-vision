# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""The planner (D45 phase 4, D47): from where a resonator or weapon is now to a target.

A plan is one resonator or weapon with two states, `current` and `target`:

* resonator -- {"ascension": 0..6, "level": 1..90, "skills": {skill: 1..10},
                 "nodes": {skill: 0..n}}
* weapon    -- {"ascension": 0..6, "level": 1..90}

The level lives inside its ascension's range (after ascension r: from the last
cap up to CAPS[r]); a state saved before levels existed counts as at its cap.
EXP for the levels between is `exp.py`'s (D52).

What it costs is the sum of the steps between the two, from the step-by-step
tables in builds.json (tools/fetch_builds.py): the six ascensions, each skill's
LV.2..LV.10, each skill's 分支强化 nodes in order, a weapon's six ascensions. All
plans together are then held against the stock like the materials page does,
lower tiers synthesising upward (materials.build_materials).

Not counted: a weapon's 贝币 per ascension (only its total is listed: it is
counted for a full 0 -> 6 plan). EXP and its 贝币 are counted (D52).

Headless: the main app renders what this returns.
"""

from __future__ import annotations

from dataclasses import asdict

from . import exp
from .catalogue import Catalogue
from .exp import CAPS
from .inventory import Item
from .materials import CURRENCY, build_materials
from .roster import avatar, weapon_summary

MAX_ASCENSION = 6
SHELLS = "贝币"


def limits(catalogue: Catalogue, kind: str, name: str) -> dict | None:
    """What can be planned for this one: ascensions, and each skill's levels and nodes."""
    build = catalogue.builds.get(f"{kind}s", {}).get(name)
    if build is None:
        return None
    out = {"ascension": len(build.get("ascension") or []) or MAX_ASCENSION}
    out["level"] = CAPS[min(out["ascension"], len(CAPS) - 1)]
    if kind == "resonator":
        out["skills"] = {skill: {"levels": len(s.get("levels") or []) + 1,
                                 "nodes": len(s.get("nodes") or [])}
                         for skill, s in (build.get("skills") or {}).items()}
    return out


def full(catalogue: Catalogue, kind: str, name: str, top: bool) -> dict:
    """The lowest (top=False) or highest (top=True) state there is."""
    lim = limits(catalogue, kind, name) or {"ascension": MAX_ASCENSION}
    state: dict = {"ascension": lim["ascension"] if top else 0,
                   "level": CAPS[min(lim["ascension"], len(CAPS) - 1)] if top else 1}
    if kind == "resonator":
        state["skills"] = {s: (v["levels"] if top else 1) for s, v in lim.get("skills", {}).items()}
        state["nodes"] = {s: (v["nodes"] if top else 0) for s, v in lim.get("skills", {}).items()}
    return state


def clamp(catalogue: Catalogue, kind: str, name: str, state: dict) -> dict:
    """`state` within what exists (a bad or stale value never reaches the maths)."""
    lim = limits(catalogue, kind, name) or {"ascension": MAX_ASCENSION}

    def num(value: object, low: int, high: int) -> int:
        try:
            return max(low, min(high, int(value)))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return low

    out: dict = {"ascension": num(state.get("ascension"), 0, lim["ascension"])}
    rank = min(out["ascension"], len(CAPS) - 1)
    low, high = (CAPS[rank - 1] if rank else 1), CAPS[rank]
    # before levels existed a state had none: at the cap it had reached
    out["level"] = num(state.get("level", high if rank else 1), low, high)
    if kind == "resonator":
        skills, nodes = state.get("skills") or {}, state.get("nodes") or {}
        out["skills"] = {s: num(skills.get(s, 1), 1, v["levels"])
                         for s, v in lim.get("skills", {}).items()}
        out["nodes"] = {s: num(nodes.get(s, 0), 0, v["nodes"])
                        for s, v in lim.get("skills", {}).items()}
    return out


def _add(total: dict[str, int], cost: dict[str, int]) -> None:
    for name, n in cost.items():
        total[name] = total.get(name, 0) + n


def cost(catalogue: Catalogue, kind: str, name: str, current: dict, target: dict) -> dict[str, int]:
    """Everything the steps from `current` to `target` take (target below current: 0)."""
    build = catalogue.builds.get(f"{kind}s", {}).get(name) or {}
    now, want = clamp(catalogue, kind, name, current), clamp(catalogue, kind, name, target)
    total: dict[str, int] = {}
    steps = build.get("ascension") or []
    for step in steps[now["ascension"]:want["ascension"]]:
        _add(total, step)
    if kind == "weapon" and now["ascension"] == 0 and want["ascension"] >= len(steps) > 0:
        shells = (build.get("materials") or {}).get(SHELLS)
        if shells:  # only the total is listed: counted for the full range
            total[SHELLS] = total.get(SHELLS, 0) + shells
    for skill, table in (build.get("skills") or {}).items():
        levels, nodes = table.get("levels") or [], table.get("nodes") or []
        # levels[0] is LV.2: from LV a to LV b costs levels[a-1 .. b-2]
        for step in levels[now["skills"][skill] - 1:want["skills"][skill] - 1]:
            _add(total, step)
        for step in nodes[now["nodes"][skill]:want["nodes"][skill]]:
            _add(total, step)
    out: dict[str, int] = {}  # summed: a wiki typo and its true name are one material
    for n, k in total.items():
        out[catalogue.canonical(n)] = out.get(catalogue.canonical(n), 0) + k
    return out


def rarity_of(catalogue: Catalogue, kind: str, name: str) -> int:
    build = catalogue.builds.get(f"{kind}s", {}).get(name) or {}
    return build.get("rarity") or (catalogue.entry(name) or {}).get("rarity") or 5


def exp_points(catalogue: Catalogue, kind: str, name: str, current: dict, target: dict) -> int:
    """EXP between the two levels (0 when the target is not above)."""
    now, want = clamp(catalogue, kind, name, current), clamp(catalogue, kind, name, target)
    return exp.needed(catalogue, kind, rarity_of(catalogue, kind, name), now["level"],
                      want["level"])


def _rows(catalogue: Catalogue, inventory: list[Item], need: dict[str, int],
          complete_tabs: set[str] | frozenset[str]) -> list[dict]:
    groups = build_materials(catalogue, inventory, complete_tabs, need=need)
    return [{**asdict(t), "shortfall": t.shortfall}
            for g in groups for t in g.tiers if t.target > 0 or t.sent_up > 0]  # a source counts


def view(catalogue: Catalogue, inventory: list[Item], plans: list[dict],
         complete_tabs: set[str] | frozenset[str] = frozenset()) -> dict:
    """Every plan with its own cost, and all of them together against the stock."""
    people = catalogue.builds.get("resonators", {})
    arms = catalogue.builds.get("weapons", {})
    total: dict[str, int] = {}
    points = {"resonator": 0, "weapon": 0}
    out = []
    for plan in plans:
        kind, name = plan["kind"], plan["name"]
        known = (people if kind == "resonator" else arms).get(name)
        need = cost(catalogue, kind, name, plan.get("current") or {}, plan.get("target") or {})
        _add(total, need)
        xp = exp_points(catalogue, kind, name, plan.get("current") or {}, plan.get("target") or {})
        points[kind] += xp
        who = (avatar(catalogue, name, known) if kind == "resonator"
               else weapon_summary(catalogue, name, known)) if known else {"name": name}
        out.append({
            "id": plan["id"], "kind": kind, "name": name, "known": known is not None,
            "who": who,
            "current": clamp(catalogue, kind, name, plan.get("current") or {}),
            "target": clamp(catalogue, kind, name, plan.get("target") or {}),
            "limits": limits(catalogue, kind, name),
            "need": sorted(
                ({"name": n, "amount": k, "icon_file": catalogue.icon_file(n),
                  "rarity": (catalogue.entry(n) or {}).get("rarity") or 0}
                 for n, k in need.items() if n not in CURRENCY),
                key=lambda m: -m["rarity"]),
            "shells": need.get(SHELLS, 0) + exp.shells_for(catalogue, kind, xp),
            "exp": xp,
        })
    rows = _rows(catalogue, inventory, total, complete_tabs) if total else []
    owned = {i.name: i.count or 0 for i in inventory if i.name}
    paid = {kind: exp.mix(n, exp.items(catalogue, kind), owned)
            for kind, n in points.items() if n}
    exp_shells = sum(exp.shells_for(catalogue, kind, n) for kind, n in points.items())
    return {
        "plans": out,
        "materials": rows,
        "shortfall": sum(r["shortfall"] for r in rows),
        "shells": total.get(SHELLS, 0) + exp_shells,
        "exp": paid,
    }
