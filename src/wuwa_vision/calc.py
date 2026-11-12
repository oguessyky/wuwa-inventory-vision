# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""计算 (D268): one resonator's panel, and every skill row's damage, heal or shield.

Headless and pure: the page and the API only hand it calc.json (`calc_data`) and a setup.
The formula is the community's (Kuro has never published one); the research is in
reports/WuWa damage and healing formulas.md and PLAN.md D268 says which parts are settled.

A setup, as kept per resonator (every share is a fraction: 0.21 is 21%):
    level, breach, skills {type: level}, nodes (the eight stat nodes taken),
    weapon {name, level, breach, rank}, echoes [{set, cost, rarity, level, main, subs}],
    buffs {bucket: value}, enemy {level, res, res_shred, def_ignore}, compare {echoes} | None
"""

from __future__ import annotations

import collections
import copy
import re

from .calc_data import STATS, SUB_TIERS

#: The buckets a buff goes into by hand (D268), as the page lists them.
BUFFS = (
    "atk_pct",
    "atk",
    "hp_pct",
    "hp",
    "def_pct",
    "def",
    "crit",
    "crit_dmg",
    "dmg_all",
    "dmg_basic",
    "dmg_heavy",
    "dmg_skill",
    "dmg_lib",
    "dmg_intro",
    "dmg_outro",
    "amplify",
    "final",
    "taken",
    "mv",
    "heal",
    "received",
    "shield",
)
#: What a panel starts from before anything is added.
START = {"crit": 0.05, "crit_dmg": 1.5, "er": 1.0}
_TERM = re.compile(r"^\s*(\d+(?:\.\d+)?)(%)?(?:\s*\*\s*(\d+))?\s*$")


def def_mult(level: int, enemy_level: int, ignore: float = 0.0) -> float:
    """The enemy's defence, as a factor: (800 + 8L) / (800 + 8L + (792 + 8L_e)(1 - ignore))."""
    mine = 800 + 8 * level
    return mine / (mine + (792 + 8 * enemy_level) * max(0.0, 1 - ignore))


def res_mult(res: float) -> float:
    """The enemy's resistance after reduction, as a factor: three branches."""
    if res < 0:
        return 1 - res / 2
    if res < 0.8:
        return 1 - res
    return 1 / (1 + 5 * res)


def expected_crit(rate: float, damage: float) -> float:
    return 1 + min(max(rate, 0.0), 1.0) * (damage - 1)


def parse_multiplier(text: str) -> dict | None:
    """'45.36%*2' -> two hits of 45.36%; '3.00%+660' -> 3% and 660 flat; '25' -> None."""
    hits: list[float] = []
    flat = 0.0
    for term in str(text).split("+"):
        found = _TERM.match(term)
        if not found:
            return None
        value, pct, times = found.groups()
        if pct:
            hits.extend([round(float(value) / 100, 6)] * int(times or 1))
        else:
            flat += float(value) * int(times or 1)
    return {"hits": hits, "flat": flat} if hits else None


def find_role(roles: dict, name: str) -> str | None:
    """The data's entry for a name the app uses: a 漂泊者 form is one entry per element."""
    if name in roles:
        return name
    if name.startswith("漂泊者"):
        element = name.rsplit("-", 1)[-1]
        key = f"漂泊者·{element}"
        if key in roles:
            return key
    return None


def default_setup(data: dict, name: str) -> dict:
    role = data["roles"][name]
    return {
        "level": 90,
        "breach": 6,
        "nodes": dict(ALL_NODES),
        "mode": None,
        "skills": {str(s["type"]): 10 for s in role.get("skills") or []},
        "weapon": {"name": None, "level": 90, "breach": 6, "rank": 1},
        "echoes": [],
        "buffs": {},
        "chain": 0,
        "toggles": {},
        "compare": None,
        "enemy": {"level": 100, "res": 0.2, "res_shred": 0.0, "def_ignore": 0.0},
    }


#: Progress keeps skill levels by the game's names; 计算 by the skill's type.
SKILL_NAMES = {"常态攻击": "1", "共鸣技能": "2", "共鸣回路": "6", "共鸣解放": "3", "变奏技能": "5"}
#: Every node taken, per skill as the detail panel draws them (D272): 共鸣回路's two are the
#: inherent skills, the others' are the stat nodes.
ALL_NODES = {kind: 2 for kind in SKILL_NAMES.values()}


def node_counts(setup: dict) -> dict[str, int]:
    """The nodes taken per skill; D269's `nodes: true/false` (the eight stat nodes, all or none)
    still opens."""
    nodes = setup.get("nodes", True)
    if isinstance(nodes, dict):
        return {kind: int(nodes.get(kind, 2)) for kind in ALL_NODES}
    return {kind: 2 if nodes or kind == "6" else 0 for kind in ALL_NODES}


def mode_of(data: dict, name: str, setup: dict) -> int | None:
    """The mode the setup chose, or the resonator's first (D272); None when they have none."""
    modes = [m["id"] for m in data["roles"][name].get("modes") or []]
    chosen = setup.get("mode")
    return chosen if chosen in modes else (modes[0] if modes else None)


#: The level each ascension stops at: the lowest ascension a level can be at.
CAPS = (20, 40, 50, 60, 70, 80, 90)


def breach_for(level: int) -> int:
    return next((b for b, cap in enumerate(CAPS) if level <= cap), len(CAPS) - 1)


def ascension_for_cap(cap: int) -> int:
    """The ascension a level cap says ("Lv 80/80": the fifth), as the game shows it (D270)."""
    return next((b for b, top in enumerate(CAPS) if cap <= top), len(CAPS) - 1)


def _scanned_echo(read: dict, data: dict) -> dict:
    """An echo as the scan read it (D270), as 计算 keeps one."""
    known = (data.get("echoes") or {}).get(read.get("name") or "") or {}
    main = (read.get("main") or [{}])[0]
    return {
        "echo": read.get("name"),
        "set": read.get("set"),
        "cost": int(read.get("cost") or known.get("cost") or 4),
        "rarity": 5,
        "level": int(read.get("level") or 0),
        "main": main.get("stat") or "crit",
        "subs": [dict(sub) for sub in read.get("subs") or []],
    }


def known(
    data: dict,
    name: str,
    progress: dict | None,
    held: list[dict],
    chain: int | None,
    scanned: dict | None = None,
) -> dict:
    """What the app already knows of this resonator (D269), as a setup to start from: the level,
    ascension and skills saved for them, the weapon a scan saw them holding, their chain -- and,
    first, what the scan read of their own screens (D270), with the game's own panel.
    `from` says which of these there were."""
    out: dict = {"from": []}
    if progress:
        out["level"] = int(progress.get("level") or 1)
        out["breach"] = int(progress.get("ascension") or breach_for(out["level"]))
        out["skills"] = {
            SKILL_NAMES[k]: int(v)
            for k, v in (progress.get("skills") or {}).items()
            if k in SKILL_NAMES
        }
        nodes = progress.get("nodes") or {}
        if nodes:
            out["nodes"] = {SKILL_NAMES[k]: int(v) for k, v in nodes.items() if k in SKILL_NAMES}
        out["from"].append("progress")
    weapons = data.get("weapons") or {}
    mine = next((w for w in held if w.get("holder") == name and w.get("name") in weapons), None)
    if mine:
        level = int(mine.get("level") or 90)
        out["weapon"] = {
            "name": mine["name"],
            "level": level,
            "breach": breach_for(level),
            "rank": int(mine.get("rank") or 1),
        }
        out["from"].append("weapon")
    if chain is not None:
        out["chain"] = int(chain)
        out["from"].append("chain")
    scanned = scanned or {}
    took = False
    attributes = scanned.get("attributes") or {}
    if attributes.get("level"):
        out["level"] = int(attributes["level"])
        out["breach"] = ascension_for_cap(int(attributes.get("cap") or attributes["level"]))
        out["panel"] = dict(attributes.get("stats") or {})
        took = True
    skills = (scanned.get("skills") or {}).get("skills") or {}
    if skills:
        out["skills"] = {
            **(out.get("skills") or {}),
            **{SKILL_NAMES[k]: int(v) for k, v in skills.items() if k in SKILL_NAMES},
        }
        took = True
    arm = scanned.get("weapon") or {}
    if arm.get("name") in weapons:
        level = int(arm.get("level") or 90)
        out["weapon"] = {
            "name": arm["name"],
            "level": level,
            "breach": ascension_for_cap(int(arm.get("cap") or level)),
            "rank": int(arm.get("rank") or 1),
        }
        took = True
    if scanned.get("echoes"):
        out["echoes"] = [_scanned_echo(e, data) for e in scanned["echoes"]]
        took = True
    if took:
        out["from"].append("scan")
    return out


def _set_counts(echoes: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for echo in echoes:
        if echo.get("set"):
            counts[echo["set"]] = counts.get(echo["set"], 0) + 1
    return counts


def available(data: dict, name: str, setup: dict, echoes: list | None = None) -> list[dict]:
    """Every buff this resonator can get with this setup (D269): the effects of the sets on
    their echoes (the 2-piece as an always-on stat), the main echo's, the weapon's passive at its
    rank, their inherent skills once their node is taken, and their chain up to its level -- of
    the chosen mode only, where there are modes (D272). Each with its words and effects."""
    role = data["roles"][name]
    out: list[dict] = []
    worn = setup.get("echoes") if echoes is None else echoes
    counts = _set_counts(worn)
    for set_name, count in counts.items():
        entry = (data.get("sets") or {}).get(set_name) or {}
        pieces_list = sorted((entry.get("buffs") or {}).items(), key=lambda kv: -int(kv[0]))
        if entry.get("two"):
            pieces_list.append(("2", entry["two"]))
        for pieces, said in pieces_list:
            if count >= int(pieces):
                buff = {
                    "id": f"set:{set_name}:{pieces}",
                    "source": "set",
                    "title": f"{set_name} {pieces}",
                    "text": (entry.get("text") or {}).get(pieces, ""),
                    "effects": said,
                }
                if pieces == "2":
                    buff["always"] = True  # a panel stat, counted there (D272)
                out.append(buff)
    first = (worn or [{}])[0].get("echo") if worn else None
    main = ((data.get("echoes") or {}).get(first or "") or {}).get("main_buff")
    if main:
        out.append(
            {
                "id": f"echo:{first}",
                "source": "echo",
                "title": first,
                "text": main["text"],
                "effects": main["effects"],
            }
        )
    weapon = setup.get("weapon") or {}
    arm = (data.get("weapons") or {}).get(weapon.get("name") or "")
    if arm and arm.get("buffs"):
        at = min(max(int(weapon.get("rank") or 1), 1), len(arm["buffs"])) - 1
        rank = arm["buffs"][at]
        out.append(
            {
                "id": f"weapon:{weapon['name']}",
                "source": "weapon",
                "title": weapon["name"],
                "text": rank["text"],
                "effects": rank["effects"],
            }
        )
    for buff in role.get("buffs") or []:
        if _unlocked(buff, data, name, setup):
            out.append(dict(buff))
    enemy = setup.get("enemy") or {}
    if enemy.get("scene") == "holo":
        holo = next(
            (h for h in data.get("holograms") or [] if h["name"] == enemy.get("name")), None
        )
        if holo and holo.get("buffs"):
            # what the fight gives the player (D274): off until switched on, being its condition
            out.append(
                {
                    "id": f"holo:{holo['name']}",
                    "source": "holo",
                    "title": holo["name"],
                    "text": holo.get("text", ""),
                    "effects": holo["buffs"],
                    "off": True,
                }
            )
    return out


def _unlocked(buff: dict, data: dict, name: str, setup: dict) -> bool:
    """A resonator's own buff or gift is there: its chain node reached, its inherent skill's
    node taken, and of the mode chosen (D272)."""
    n = int(buff.get("n") or 0)
    if buff["source"] == "chain" and n > int(setup.get("chain") or 0):
        return False
    if buff["source"] == "inherent" and n > node_counts(setup)["6"]:
        return False
    return "mode" not in buff or buff["mode"] == mode_of(data, name, setup)


def gives(data: dict, name: str, setup: dict, stats: dict) -> list[dict]:
    """What this resonator gives the others with this setup (D272), and, where a limit needs
    a stat, whether the panel reaches it."""
    out = []
    for given in data["roles"][name].get("gives") or []:
        if not _unlocked(given, data, name, setup):
            continue
        given = copy.deepcopy(given)
        for need in given.get("needs") or []:
            have = float(stats.get(need["stat"]) or 0)
            need.update(have=have, met=have >= need["value"] - 1e-9)
        out.append(given)
    return out


#: A buff's stat that is the enemy's, not the resonator's.
_ENEMY = {"def_ignore", "res_shred"}


def _apply(
    listed: list[dict], toggles: dict, element: int | None = None
) -> tuple[dict, dict, list[dict]]:
    """The buffs that are on -- every one listed, unless switched off (D272): what they add to
    the buffs, to the enemy, and the effects for one kind of hit or one skill only. An amplify
    of another element than the resonator's counts for nothing."""
    buffs: dict[str, float] = {}
    enemy: dict[str, float] = {}
    scoped: list[dict] = []
    for buff in listed:
        said = toggles.get(buff["id"]) or {}
        if buff.get("always"):
            buff["on"] = True
        else:
            buff["on"] = bool(said["on"]) if "on" in said else not buff.get("off")
        if not buff["on"] or buff.get("always"):
            continue
        values = said.get("values") or []
        for i, effect in enumerate(buff["effects"]):
            if effect.get("element") and element and effect["element"] != element:
                continue
            given = values[i] if i < len(values) else None
            value = float(given) if given is not None else effect["value"]
            if effect.get("per_stack"):
                value *= int(said.get("stacks") or effect.get("stacks") or 1)
            if effect.get("kind") or effect.get("skill"):
                scoped.append({**effect, "value": value})
            elif effect["stat"] in _ENEMY:
                enemy[effect["stat"]] = enemy.get(effect["stat"], 0.0) + value
            else:
                buffs[effect["stat"]] = buffs.get(effect["stat"], 0.0) + value
    return buffs, enemy, scoped


def _with_buffs(setup: dict, buffs: dict, enemy: dict) -> dict:
    out = dict(setup)
    out["buffs"] = {**(setup.get("buffs") or {})}
    for key, value in buffs.items():
        out["buffs"][key] = float(out["buffs"].get(key) or 0) + value
    out["enemy"] = {**(setup.get("enemy") or {})}
    for key, value in enemy.items():
        out["enemy"][key] = float(out["enemy"].get(key) or 0) + value
    return out


def _ratio(table: dict, level: int, breach: int, default: float = 1.0) -> object:
    return table.get(f"{level}/{breach}", default)


def panel(data: dict, setup: dict, echoes: list | None = None) -> dict:
    """The resonator's stats with every bonus that is always on, and the buffs entered."""
    role = data["roles"][setup["_role"]] if "_role" in setup else _only_role(data, setup)
    level, breach = int(setup.get("level", 90)), int(setup.get("breach", 6))
    hp_r, atk_r, def_r = _ratio(data["role_growth"], level, breach, [1.0, 1.0, 1.0])
    out: dict[str, float] = {k: 0.0 for k in STATS}
    out.update(START)
    base = {
        "hp": role["base"]["hp"] * hp_r,
        "atk": role["base"]["atk"] * atk_r,
        "def": role["base"]["def"] * def_r,
    }

    def add(key: str, value: float) -> None:
        out[key] = out.get(key, 0.0) + float(value)

    weapon = setup.get("weapon") or {}
    arm = (data.get("weapons") or {}).get(weapon.get("name") or "")
    if arm:
        at = (int(weapon.get("level", 90)), int(weapon.get("breach", 6)))
        base["atk"] += arm["atk"] * _ratio(data["weapon_growth"].get(arm["atk_curve"], {}), *at)
        if arm.get("sub"):
            add(
                arm["sub"]["stat"],
                arm["sub"]["value"] * _ratio(data["weapon_growth"].get(arm["sub_curve"], {}), *at),
            )
    counts = node_counts(setup)
    for node in role.get("nodes") or []:
        # a node under a skill counts once that skill's nodes reach it (D272); one the data
        # could not place counts when all of them are taken
        if "skill" in node:
            taken = counts.get(node["skill"], 0) >= int(node.get("tier") or 1)
        else:
            taken = all(counts[k] >= 2 for k in ("1", "2", "3", "5"))
        if taken:
            add(node["stat"], node["value"])

    growth = (data.get("echo") or {}).get("growth") or [1.0]
    sets: dict[str, int] = {}
    for echo in setup.get("echoes") if echoes is None else echoes:
        rarity, cost = str(echo.get("rarity", 5)), str(echo.get("cost", 4))
        grow = growth[min(int(echo.get("level", 25)), len(growth) - 1)]
        mains = ((data["echo"]["main"].get(rarity) or {}).get(cost)) or []
        main = next((m for m in mains if m["stat"] == echo.get("main")), None)
        if main:
            add(main["stat"], main["value"] * grow)
        fixed = (data["echo"]["fixed"].get(rarity) or {}).get(cost)
        if fixed:
            add(fixed["stat"], fixed["value"] * grow)
        for sub in echo.get("subs") or []:
            if sub.get("stat"):
                add(sub["stat"], sub.get("value") or 0)
        if echo.get("set"):
            sets[echo["set"]] = sets.get(echo["set"], 0) + 1
    for name, count in sets.items():
        if count >= 2:
            for bonus in ((data.get("sets") or {}).get(name) or {}).get("two") or []:
                add(bonus["stat"], bonus["value"])

    buffs = setup.get("buffs") or {}
    for key in (
        "atk_pct",
        "atk",
        "hp_pct",
        "hp",
        "def_pct",
        "def",
        "crit",
        "crit_dmg",
        "er",
        "heal",
        "dmg_all",
        "dmg_basic",
        "dmg_heavy",
        "dmg_skill",
        "dmg_lib",
        "dmg_intro",
        "dmg_outro",
        *(f"dmg_{e}" for e in range(1, 7)),
    ):
        add(key, buffs.get(key) or 0)

    for key in ("hp", "atk", "def"):
        out[f"base_{key}"] = base[key]
        out[f"bonus_{key}"] = out[key]
        out[key] = base[key] * (1 + out[f"{key}_pct"]) + out[key]
    return out


def _only_role(data: dict, setup: dict) -> dict:
    return data["roles"][setup["role"]] if setup.get("role") else next(iter(data["roles"].values()))


def _for_row(scoped: list[dict], skill: dict, row: dict) -> dict[str, float]:
    """The effects for one kind of hit or one skill (D269) that this row is."""
    out: dict[str, float] = {}
    for effect in scoped:
        if effect.get("kind") and effect["kind"] != row.get("bonus"):
            continue
        named = effect.get("skill")
        if named and named != skill["name"] and named not in row["name"]:
            continue
        out[effect["stat"]] = out.get(effect["stat"], 0.0) + effect["value"]
    return out


def _rows(
    data: dict, role: dict, setup: dict, stats: dict, scoped: list[dict] | None = None
) -> list[dict]:
    buffs = setup.get("buffs") or {}
    enemy = setup.get("enemy") or {}
    level = int(setup.get("level", 90))
    ignore = float(enemy.get("def_ignore") or 0)
    shred = float(enemy.get("res_shred") or 0)
    element = f"dmg_{role['element']}"
    out = []
    for skill in role.get("skills") or []:
        at = int((setup.get("skills") or {}).get(str(skill["type"]), 10))
        rows = []
        for row in skill["rows"]:
            text = row["values"][min(max(at, 1), len(row["values"])) - 1]
            said = parse_multiplier(text)
            if said is None:
                continue
            scale = stats[row.get("stat") or "atk"]
            extra = _for_row(scoped or [], skill, row)
            mv = sum(said["hits"]) * (1 + float(buffs.get("mv") or 0) + extra.get("mv", 0))
            defence = def_mult(
                level, int(enemy.get("level", 100)), ignore + extra.get("def_ignore", 0)
            )
            resist = res_mult(float(enemy.get("res", 0.2)) - shred - extra.get("res_shred", 0))
            entry = {
                "name": row["name"],
                "kind": row["kind"],
                "multiplier": text,
                "bonus": row.get("bonus"),
            }
            if row["kind"] == "damage":
                kind = f"dmg_{row.get('bonus')}"
                bonus = stats.get("dmg_all", 0) + stats.get(element, 0) + stats.get(kind, 0)
                bonus += extra.get("dmg_all", 0) + extra.get(element, 0) + extra.get(kind, 0)
                crit = stats["crit"] + extra.get("crit", 0)
                crit_dmg = stats["crit_dmg"] + extra.get("crit_dmg", 0)
                noncrit = (
                    (scale * mv + said["flat"])
                    * (1 + bonus)
                    * (1 + float(buffs.get("amplify") or 0) + extra.get("amplify", 0))
                    * (1 + float(buffs.get("final") or 0) + extra.get("final", 0))
                    * (1 + float(buffs.get("taken") or 0))
                    * defence
                    * resist
                )
                entry.update(
                    noncrit=noncrit,
                    crit=noncrit * crit_dmg,
                    expected=noncrit * expected_crit(crit, crit_dmg),
                )
            elif row["kind"] == "heal":
                entry["amount"] = (scale * mv + said["flat"]) * (
                    1 + stats.get("heal", 0) + float(buffs.get("received") or 0)
                )
            else:
                entry["amount"] = (scale * mv + said["flat"]) * (
                    1 + float(buffs.get("shield") or 0)
                )
            rows.append(entry)
        if rows:
            out.append({"type": skill["type"], "name": skill["name"], "level": at, "rows": rows})
    return out


def compute(
    data: dict, setup: dict, name: str | None = None, game: dict | None = None, _grade: bool = True
) -> dict:
    """The panel and every row, with the buffs switched on (D269); with `compare`, the same
    again on B -- A with its echoes, weapon or chain changed (D273) -- each row's change against
    A as a share. A stat typed into the panel is used as it is (D273)."""
    setup = dict(setup)
    if name:
        setup["_role"] = name
    role_name = setup["_role"] if "_role" in setup else next(iter(data["roles"]))
    role = data["roles"][role_name]
    toggles = setup.get("toggles") or {}
    typed = {k: float(v) for k, v in (setup.get("panel") or {}).items() if v is not None}

    def side(base: dict, worked: dict | None = None) -> tuple[dict, list, list, dict, dict]:
        listed = available(data, role_name, base)
        buffs, enemy, scoped = _apply(listed, toggles, role.get("element"))
        mine = _with_buffs(base, buffs, enemy)
        stats = panel(data, mine)
        raw = dict(stats)
        for key, value in typed.items():
            # B keeps A's typed number, moved by what B changed (D273)
            stats[key] = value + (stats[key] - worked[key] if worked else 0.0)
        return stats, _rows(data, role, mine, stats, scoped), listed, mine, raw

    stats, skills, listed, mine, raw = side(setup)
    enemy = mine.get("enemy") or {}
    defence = def_mult(
        int(setup.get("level", 90)),
        int(enemy.get("level", 100)),
        float(enemy.get("def_ignore") or 0),
    )
    said = {
        "panel": stats,
        "typed": sorted(typed),
        "skills": skills,
        "buffs": listed,
        "compare": None,
        "enemy": {**enemy, "def": defence},
        "gives": gives(data, role_name, setup, stats),
        "mode": mode_of(data, role_name, setup),
        "grade": _graded(data, role_name, setup, typed, game) if _grade else None,
        "rates": [rate_echo(data, role_name, e, setup) for e in setup.get("echoes") or []]
        if _grade
        else [],
    }
    compare = setup.get("compare") or {}
    if compare:
        other = dict(setup)
        for key in ("echoes", "weapon", "chain"):
            if compare.get(key) is not None:
                other[key] = compare[key]
        theirs, their_skills, their_buffs, _, _ = side(other, raw)
        said["compare"] = {
            "panel": theirs,
            "skills": _with_change(skills, their_skills),
            "buffs": their_buffs,
            "changed": _changed(setup, other),
        }
    return said


def _graded(data: dict, name: str, setup: dict, typed: dict, game: dict | None) -> dict:
    """The grade (D274) on the panel typed in, else the game's own as scanned, else the one
    worked out."""
    worked = panel(data, {**setup, "_role": name})
    if typed:
        stats, source, judged = {**worked, **typed}, "typed", setup
    elif game:
        stats, source, judged = {**worked, **game}, "game", {**setup, "panel": dict(game)}
    else:
        stats, source, judged = worked, "worked", setup
    return {**grade(data, name, judged, stats), "panel_from": source}


def _changed(a: dict, b: dict) -> dict:
    """What B changed from A (D273): the echo slots, the weapon's name, the chain from and to."""
    out: dict = {}
    mine, theirs = a.get("echoes") or [], b.get("echoes") or []
    slots = [
        i
        for i in range(max(len(mine), len(theirs)))
        if (mine[i] if i < len(mine) else None) != (theirs[i] if i < len(theirs) else None)
    ]
    if slots:
        out["echoes"] = slots
    if (a.get("weapon") or {}) != (b.get("weapon") or {}):
        out["weapon"] = (b.get("weapon") or {}).get("name")
    if int(a.get("chain") or 0) != int(b.get("chain") or 0):
        out["chain"] = [int(a.get("chain") or 0), int(b.get("chain") or 0)]
    return out


def graduated(data: dict, name: str, setup: dict) -> bool:
    """大毕业, as far as a setup can say it (D273): level 90 and its ascension, every skill at 10
    with every node, the weapon at 90, and five echoes at +25 and 5★ filling the 12 cost."""
    skills = setup.get("skills") or {}
    weapon = setup.get("weapon") or {}
    echoes = setup.get("echoes") or []
    # the skills this resonator has levels for
    own = [
        str(s["type"])
        for s in data["roles"][name].get("skills") or []
        if str(s["type"]) in SKILL_NAMES.values()
    ]
    return (
        int(setup.get("level") or 0) >= 90
        and int(setup.get("breach") or 0) >= 6
        and all(int(skills.get(kind) or 0) >= 10 for kind in own)
        and all(n >= 2 for n in node_counts(setup).values())
        and bool(weapon.get("name"))
        and int(weapon.get("level") or 0) >= 90
        and len(echoes) == 5
        and all(int(e.get("level") or 0) >= 25 and int(e.get("rarity") or 0) >= 5 for e in echoes)
        and sum(int(e.get("cost") or 0) for e in echoes) == 12
    )


def set_gives(entry: dict) -> str | None:
    """What a set gives, for the echo picker's 套装效果 (D273): its 2-piece stat, or for a set
    of three, the first effect its smallest count reads as."""
    if entry.get("two"):
        return entry["two"][0]["stat"]
    for _, said in sorted((entry.get("buffs") or {}).items(), key=lambda kv: int(kv[0])):
        if said:
            return said[0]["stat"]
    return None


#: The lines (D274): 大毕业 at 90% of their own best, 小毕业 at 80%; a cap in their words is
#: 小毕业 at 85% of it.
BIG, SMALL = 0.9, 0.8
LIMIT_SMALL = 0.85


def basis(data: dict, name: str, setup: dict) -> str:
    """What a resonator is judged by (D274): a cap in their own words, else their healing for one
    the game tags 生存治疗, else their damage -- whatever the tags say they are."""
    if _limits_of(data["roles"][name], setup):
        return "limit"
    return _puts_out(data, name)


def _puts_out(data: dict, name: str) -> str:
    """What a resonator's output is (D274, D275): their heals for one the game tags 生存治疗 --
    cap or no cap -- else their damage."""
    role = data["roles"][name]
    tags = role.get("tags") or []
    heals = any(row.get("kind") == "heal" for s in role.get("skills") or [] for row in s["rows"])
    # a healer who also names a kind of damage they deal (尤诺's 共鸣解放伤害) is judged by it
    deals = any(t.endswith("伤害") and not t.endswith("加深") for t in tags)
    return "heal" if "生存治疗" in tags and heals and not deals else "damage"


def _heal_stat(role: dict) -> str:
    """The stat most of a healer's heals are worked from (D275): 维里奈's ATK, 守岸人's HP."""
    rows = [row for skill in role.get("skills") or [] for row in skill["rows"]]
    heals = collections.Counter(row.get("stat") for row in rows if row["kind"] == "heal")
    return heals.most_common(1)[0][0] if heals else "atk"


def _built_on(data: dict, name: str, setup: dict) -> list[str]:
    """What a grade is built from, for the box to say (D275): a cap's stat, then the stat their
    heals are worked from and 治疗效果加成, or the stat their hits are and crit."""
    role = data["roles"][name]
    out = [limit["stat"] for limit in _limits_of(role, setup)]
    kind = _puts_out(data, name)
    if kind == "heal":
        return out + [_heal_stat(role), "heal"]
    if out:
        return out
    rows = [row for skill in role.get("skills") or [] for row in skill["rows"]]
    kinds = collections.Counter(row.get("bonus") for row in rows if row["kind"] == "damage")
    on = [role.get("scales") or "atk", "crit", "crit_dmg"]
    return on + ([f"dmg_{kinds.most_common(1)[0][0]}"] if kinds else [])


def _limits_of(role: dict, setup: dict) -> list[dict]:
    chain = int(setup.get("chain") or 0)
    best: dict[str, float] = {}
    for limit in role.get("limits") or []:
        if int(limit.get("n") or 0) > chain:
            continue
        best[limit["stat"]] = max(best.get(limit["stat"], 0.0), float(limit["value"]))
    return [{"stat": k, "value": v} for k, v in best.items()]


def grade_for(ratio: float) -> str | None:
    """大毕业 at 90% of their own best, 小毕业 at 80% (D274)."""
    return "大毕业" if ratio >= BIG - 1e-9 else "小毕业" if ratio >= SMALL - 1e-9 else None


def _output(result: dict, kind: str) -> float:
    """What a resonator puts out (D274): every damage row's expected damage, or every heal."""
    rows = [row for skill in result["skills"] for row in skill["rows"]]
    if kind == "heal":
        return sum(row.get("amount") or 0 for row in rows if row["kind"] == "heal")
    return sum(row.get("expected") or 0 for row in rows if row["kind"] == "damage")


def grade(data: dict, name: str, setup: dict, stats: dict | None = None) -> dict:
    """小毕业 or 大毕业 (D274, D275). A cap in their own words is judged on the panel given; their
    output -- for a healer, cap or no cap -- against the same resonator at its best
    (`best_setup`). Every line must be met."""
    role = data["roles"][name]
    kind = basis(data, name, setup)
    output = _puts_out(data, name)
    lines: list[dict] = []
    limits = _limits_of(role, setup)
    if limits:
        stats = stats if stats is not None else panel(data, {**setup, "_role": name})
    for limit in limits:
        have = float(stats.get(limit["stat"]) or 0)
        need = limit["value"]
        small = round(need * LIMIT_SMALL, 4)
        lines.append(
            {
                "stat": limit["stat"],
                "small": small,
                "need": need,
                "have": have,
                "met": have >= need - 1e-9,
                "met_small": have >= small - 1e-9,
            }
        )
    if not limits or output == "heal":
        now = _output(compute(data, setup, name, _grade=False), output)
        best = _output(compute(data, best_setup(data, name, setup), name, _grade=False), output)
        ratio = now / best if best else 0.0
        lines.append(
            {
                "stat": output,
                "small": SMALL,
                "need": BIG,
                "have": ratio,
                "met": ratio >= BIG - 1e-9,
                "met_small": ratio >= SMALL - 1e-9,
                "now": now,
                "best": best,
            }
        )
    said = (
        "大毕业"
        if all(x["met"] for x in lines)
        else "小毕业"
        if all(x["met_small"] for x in lines)
        else None
    )
    echoes = setup.get("echoes") or []
    missing = []
    if int(setup.get("level") or 0) < 90:
        missing.append("level")
    if len(echoes) < 5 or any(int(e.get("level") or 0) < 25 for e in echoes):
        missing.append("echoes")
    return {
        "grade": said,
        "basis": kind,
        "on": _built_on(data, name, setup),
        "lines": lines,
        "missing": missing,
    }


#: The order a best build fills its five substats in, when they count (D274).
_SUB_ORDER = (
    "crit",
    "crit_dmg",
    "atk_pct",
    "hp_pct",
    "def_pct",
    "er",
    "dmg_basic",
    "dmg_heavy",
    "dmg_skill",
    "dmg_lib",
    "atk",
    "hp",
    "def",
)


def _useful(data: dict, name: str, setup: dict) -> set[str]:
    """The substats their best build is made of (D274, D275): their 有效词条 -- a cap's stat, and
    for a healer 共鸣效率 and the stat their heals are worked from."""
    role = data["roles"][name]
    kind = _puts_out(data, name)
    rows = [row for skill in role.get("skills") or [] for row in skill["rows"]]
    capped = {limit["stat"] for limit in _limits_of(role, setup)}
    if kind == "heal":
        return capped | {"er", f"{_heal_stat(role)}_pct"}
    if capped:
        return capped
    scales = role.get("scales") or "atk"
    kinds = collections.Counter(row.get("bonus") for row in rows if row["kind"] == "damage")
    out = {"crit", "crit_dmg", f"{scales}_pct"}
    if kinds:
        out.add(f"dmg_{kinds.most_common(1)[0][0]}")
    return out


def best_setup(data: dict, name: str, setup: dict) -> dict:
    """The same resonator at its best (D274): level 90, every skill at 10 with every node, the same
    weapon at 90, five echoes at +25 filling the 12 cost in the same sets, each main stat the one
    that gives most, and five 有效词条 at their top roll -- the ones it lacks filled from the next
    that count."""
    kind = _puts_out(data, name)
    useful = _useful(data, name, setup)
    order = sorted(
        SUB_TIERS, key=lambda k: (k not in useful, _SUB_ORDER.index(k) if k in _SUB_ORDER else 99)
    )
    subs = [{"stat": k, "value": SUB_TIERS[k][-1]} for k in order[:5]]
    best = copy.deepcopy(setup)
    best.pop("panel", None)
    best.pop("compare", None)
    best.update(
        level=90,
        breach=6,
        nodes=dict(ALL_NODES),
        skills={k: 10 for k in (setup.get("skills") or {})},
    )
    if (best.get("weapon") or {}).get("name"):
        best["weapon"] = {**best["weapon"], "level": 90, "breach": 6}
    worn = setup.get("echoes") or []
    sets = [e.get("set") for e in worn] + [None] * 5
    best["echoes"] = [
        {
            "echo": (worn[i].get("echo") if i < len(worn) else None),
            "set": sets[i],
            "cost": cost,
            "rarity": 5,
            "level": 25,
            "main": None,
            "subs": copy.deepcopy(subs),
        }
        for i, cost in enumerate((4, 3, 3, 1, 1))
    ]
    # each main stat, the one that gives most with the others as they stand
    for echo in best["echoes"]:
        options = [
            m["stat"] for m in (data["echo"]["main"].get("5") or {}).get(str(echo["cost"]), [])
        ]
        scored = []
        for option in options or [None]:
            echo["main"] = option
            scored.append((_output(compute(data, best, name, _grade=False), kind), option))
        echo["main"] = max(scored, key=lambda x: x[0])[1]
    return best


def rate_echo(data: dict, name: str, echo: dict, setup: dict | None = None) -> dict:
    """One echo for the resonator wearing it (D274): each substat's tier of the ones it can roll,
    whether it is 有效, how many are, and how full those rolled."""
    useful = _useful(data, name, setup or {})
    subs = []
    for sub in echo.get("subs") or []:
        tiers = SUB_TIERS.get(sub.get("stat") or "")
        value = float(sub.get("value") or 0)
        entry = {"stat": sub.get("stat"), "value": value, "useful": sub.get("stat") in useful}
        if tiers:
            nearest = min(range(len(tiers)), key=lambda i: abs(tiers[i] - value))
            entry.update(tier=nearest + 1, tiers=len(tiers), min=tiers[0], max=tiers[-1])
        subs.append(entry)
    counted = [s for s in subs if s["useful"] and s.get("max")]
    fill = sum(s["value"] / s["max"] for s in counted) / len(counted) if counted else 0.0
    return {"subs": subs, "useful": len(counted), "fill": fill}


def hologram_res(hologram: dict, element: int) -> float:
    """A 全息's resistance against an element (D273): the game says only which are raised, so a
    raised one counts as an overworld boss's own element does (40%), the rest 10%."""
    return 0.4 if element in (hologram.get("raised") or []) else 0.1


def _with_change(mine: list[dict], theirs: list[dict]) -> list[dict]:
    out = copy.deepcopy(theirs)
    for a_skill, b_skill in zip(mine, out, strict=True):
        for a, b in zip(a_skill["rows"], b_skill["rows"], strict=True):
            key = "expected" if "expected" in a else "amount"
            b["change"] = (b[key] / a[key] - 1) if a[key] else 0.0
    return out
