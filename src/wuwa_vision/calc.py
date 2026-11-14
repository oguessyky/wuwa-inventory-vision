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

from . import calc_data
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
    # D304: everything else 计算 counts -- 共鸣效率, the resonator's own element, a 加深 for one
    # kind of hit, the enemy's defence and resistance, and the energy a round runs on
    "er",
    "tune_eff",
    "dmg_elem",
    "amplify_basic",
    "amplify_heavy",
    "amplify_skill",
    "amplify_lib",
    "amplify_intro",
    "amplify_outro",
    "def_ignore",
    "res_shred",
    "energy",
    "concerto",
)
#: What a panel starts from before anything is added.
START = {"crit": 0.05, "crit_dmg": 1.5, "er": 1.0, "tune_eff": 1.0}
#: The game's tags of one who tunes (D311): only they start at 100% 偏谐值累积效率.
TUNERS = {"集谐响应", "震谐响应", "骇破响应", "偏谐值累积效率"}
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


def _echo_key(echo: dict) -> tuple:
    """An echo as it is compared with the one read (D284): what it is and what it rolled, a
    value to four places -- the scan reads more of them than a field is typed to."""
    return (
        echo.get("echo"),
        echo.get("set"),
        int(echo.get("cost") or 0),
        int(echo.get("rarity") or 5),
        int(echo.get("level") or 0),
        echo.get("main"),
        tuple(
            (s.get("stat"), round(float(s.get("value") or 0), 4)) for s in echo.get("subs") or []
        ),
    )


def edited(setup: dict, known: dict) -> list[str]:
    """Each field of a setup changed by hand from what the app knows of the resonator (D284):
    `level` (with its ascension), `skills.<type>`, `nodes`, `chain`, `weapon.name`,
    `weapon.level`, `weapon.rank`, `echoes.<slot>`. Only what is known can be edited against;
    buffs, toggles and the enemy are 计算's own."""
    out: list[str] = []
    if "level" in known and (int(setup.get("level") or 0), int(setup.get("breach") or 0)) != (
        int(known["level"]),
        int(known.get("breach") or 0),
    ):
        out.append("level")
    skills = setup.get("skills") or {}
    for kind, value in (known.get("skills") or {}).items():
        if int(skills.get(kind, 10)) != int(value):
            out.append(f"skills.{kind}")
    nodes = setup.get("nodes")
    if (
        isinstance(known.get("nodes"), dict)
        and isinstance(nodes, dict)
        and any(int(nodes.get(k, 0)) != int(v) for k, v in known["nodes"].items())
    ):
        out.append("nodes")
    if "chain" in known and int(setup.get("chain") or 0) != int(known["chain"]):
        out.append("chain")
    weapon, read = setup.get("weapon") or {}, known.get("weapon")
    if read:
        if weapon.get("name") != read["name"]:
            out.append("weapon.name")
        if (weapon.get("level"), weapon.get("breach")) != (read["level"], read["breach"]):
            out.append("weapon.level")
        if weapon.get("rank") != read["rank"]:
            out.append("weapon.rank")
    elif weapon.get("name"):
        # none known: holding one is the change, and none is the way back (D309)
        out.append("weapon.name")
    if "echoes" in known:
        mine, theirs = setup.get("echoes") or [], known["echoes"] or []
        for i in range(max(len(mine), len(theirs))):
            if i >= len(mine) or i >= len(theirs) or _echo_key(mine[i]) != _echo_key(theirs[i]):
                out.append(f"echoes.{i}")
    return out


def own_changes(data: dict, name: str, setup: dict) -> list[str]:
    """计算's own settings changed from a setup never touched (D290): `mode` (only when it is not
    the one used anyway), `enemy`, `toggles.<id>` (a buff switched from where it starts, or its
    numbers or stacks typed), `buffs.<key>` (a manual buff), `panel.<key>` (a stat typed in).
    With `edited`, everything the page can say was changed, and put back."""
    out: list[str] = []
    if setup.get("mode") is not None and mode_of(data, name, setup) != mode_of(
        data, name, {**setup, "mode": None}
    ):
        out.append("mode")
    if (setup.get("enemy") or {}) != default_setup(data, name)["enemy"]:
        out.append("enemy")
    listed = available(data, name, setup)
    starts = {b["id"]: not b.get("off") for b in listed if not b.get("always")}
    for buff_id, said in (setup.get("toggles") or {}).items():
        said = said or {}
        switched = "on" in said and buff_id in starts and bool(said["on"]) != starts[buff_id]
        typed = any(v is not None for v in said.get("values") or [])
        typed = typed or said.get("stacks") is not None
        if switched or typed:
            out.append(f"toggles.{buff_id}")
    out += [f"buffs.{k}" for k, v in (setup.get("buffs") or {}).items() if v]
    out += [f"panel.{k}" for k, v in (setup.get("panel") or {}).items() if v is not None]
    return out


def panel_holds(changed: list[str]) -> bool:
    """Whether the game's panel, as scanned, is still this setup's (D284): a skill's level is
    not on the panel; the level, nodes, chain, weapon and echoes all are."""
    return all(key.startswith("skills.") for key in changed)


def _set_counts(echoes: list[dict]) -> dict[str, int]:
    """Each set's pieces among the echoes worn, as the game counts them (D302): an echo worn
    twice is one piece of its set. An echo with no name written counts on its own."""
    counts: dict[str, int] = {}
    seen: set[tuple[str, str]] = set()
    for echo in echoes or []:
        name = echo.get("set")
        if not name:
            continue
        if echo.get("echo"):
            if (name, echo["echo"]) in seen:
                continue
            seen.add((name, echo["echo"]))
        counts[name] = counts.get(name, 0) + 1
    return counts


#: An echo unlocks a substat every this many levels: one at Lv.5, five at Lv.25 (D302).
SUB_EVERY = 5


def unlocked_subs(echo: dict) -> list[dict]:
    """The substats this echo's level has unlocked (D302); one written past them is kept in the
    setup, and not counted. An echo with no level written is a full one."""
    level = int(echo.get("level", 25) or 0)
    return list(echo.get("subs") or [])[: max(level, 0) // SUB_EVERY]


def _pieces(entry: dict) -> list[int]:
    """The pieces a set has a bonus at: 2 and 5, or 3, or 1 (D302)."""
    said = {*(entry.get("text") or {}), *(entry.get("buffs") or {})}
    if entry.get("two"):
        said.add("2")
    return sorted(int(p) for p in said if str(p).isdigit())


def set_tally(data: dict, echoes: list[dict]) -> list[dict]:
    """The sets worn (D302): each one's pieces as the game counts them, the pieces it has a bonus
    at, and which of those are on -- two sets at once from 3+2 or 2+2+1. The most pieces first."""
    counts = _set_counts(echoes)
    out = []
    for name, count in counts.items():
        pieces = _pieces((data.get("sets") or {}).get(name) or {})
        out.append({"name": name, "count": count, "pieces": pieces,
                    "on": [p for p in pieces if count >= p]})
    return sorted(out, key=lambda s: -s["count"])


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
                    # read by hand, and what was noted (D305)
                    "checked": bool((entry.get("checked") or {}).get(pieces)),
                    "notes": list((entry.get("notes") or {}).get(pieces) or []),
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
                "checked": bool(main.get("checked")),
                "notes": list(main.get("notes") or []),
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
                "checked": bool(arm.get("checked")),
                "notes": list(rank.get("not_counted") or []),
            }
        )
    for buff in role.get("buffs") or []:
        if _unlocked(buff, data, name, setup):
            out.append(dict(buff))
    # what the others in a team give them (D287): listed like their own, on until switched off
    for given in setup.get("_given") or []:
        out.append(copy.deepcopy(given))
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


def _of_mode(buffs: list[dict], mode: int | None) -> list[dict]:
    """Each buff with only the effects of the mode chosen (D314): a reading by hand can give one
    paragraph two states' effects -- 菲比's 赦罪 and 告解."""
    out = []
    for buff in buffs:
        effects = buff.get("effects") or []
        if any(e.get("mode") is not None for e in effects):
            buff = {**buff, "effects": [e for e in effects if e.get("mode") in (None, mode)]}
        out.append(buff)
    return out


#: Stats that are an amount, not a share: written in their words without a %.
_FLAT_STATS = {"atk", "hp", "def", "energy", "concerto"}
#: Seconds on the field each round, by what a resonator is in a team (D315): changeable per setup.
FIELD = {"主C": 14.0, "副C": 7.0, "辅助": 4.0}
#: What is done once a turn on the field: a buff it starts lasts its seconds, not throughout.
_ONCE = ("变奏", "入场", "共鸣解放", "延奏", "声骸技能")
#: What is done again and again in a turn: a buff it starts is up throughout.
_OFTEN = ("普攻", "重击", "共鸣技能", "空中攻击", "治疗", "护盾", "附加")
_LASTS = re.compile(r"持续(\d+(?:\.\d+)?)秒")
_RATE = re.compile(
    r"每(\d*(?:\.\d+)?)秒(?:可|最多|至多)?(?:通过\S{0,8})?(?:获得|叠加|获取|触发)(\d+)[层次]")
_GROWS = re.compile(r"延长(\d+(?:\.\d+)?)秒(?:，最多可延长(\d+)次)?")
_FULL_AT = re.compile(r"(?:为|达到|叠满)(\d+)层(?:时|后)")
_NAMED = re.compile(r"【([^】]+)】")


def kind_of(data: dict, name: str, setup: dict) -> str:
    """主C, 副C or 辅助 (D315): what the chosen mode says it is (菲比's 告解, D314), else what the
    hand list says, else a healer is 辅助 and anyone else 主C."""
    role = data["roles"][name]
    mode = mode_of(data, name, setup)
    for m in role.get("modes") or []:
        if m.get("id") == mode:
            said = next((k for k in FIELD if k in (m.get("text") or "")), None)
            if said:
                return said
    if role.get("kind") in FIELD:
        return role["kind"]
    return "辅助" if _puts_out(data, name) == "heal" else "主C"


def field_of(data: dict, name: str, setup: dict) -> float:
    """A resonator's seconds on the field each round (D315): as typed, else by what they are."""
    if setup.get("field"):
        return float(setup["field"])
    return FIELD[kind_of(data, name, setup)]


def _mark(effect: dict) -> str:
    value = float(effect.get("value") or 0)
    if effect.get("stat") in _FLAT_STATS:
        return f"{value:g}"
    return f"{round(value * 100, 2):g}%"


def timing(text: str, effects: list[dict]) -> list[dict]:
    """How each effect of a buff runs, from its words (D315): how long it lasts once started
    (`seconds`), whether what starts it happens throughout a turn (`refresh`, a hit or a heal) or
    once (an intro, an outro, 共鸣解放), whether switching out or a count ends its stacks
    (`switch`, `clears`), how fast they come (`rate` a second) and, for one that needs its stacks
    full, how many (`full_only`). Each effect is found by its number in its own sentence."""
    sentences = [s for s in re.split(r"(?<=[。；;\n])", text or "") if s.strip()]
    used: dict[tuple[int, str], int] = {}
    at = 0
    out = []
    for effect in effects:
        mark = _mark(effect)
        found = None
        for j in [*range(at, len(sentences)), *range(at)]:
            if sentences[j].count(mark) > used.get((j, mark), 0):
                found = j
                break
        if found is not None:
            used[(found, mark)] = used.get((found, mark), 0) + 1
            at = found
        out.append(_timing_at(sentences, found if found is not None else at))
    return out


def _timing_at(sentences: list[str], i: int) -> dict:
    own = sentences[i] if i < len(sentences) else ""
    names = set(_NAMED.findall(own))
    related = [s for s in sentences if s == own or names & set(_NAMED.findall(s))]
    whole = "".join(related)
    lasts = _LASTS.search(own) or _LASTS.search(whole)
    rate = _RATE.search(whole)
    full = _FULL_AT.search(own)
    # "…持续8秒；施放共鸣技能时，该效果延长5秒，最多可延长3次": it lasts as long as it can grow
    after = sentences[i + 1] if i + 1 < len(sentences) else ""
    grows = _GROWS.search(after) if "该效果" in after else None
    if lasts and grows:
        lasts_for = float(lasts.group(1)) + float(grows.group(1)) * int(grows.group(2) or 1)
    else:
        lasts_for = float(lasts.group(1)) if lasts else None
    clauses = [c for s in related for c in re.split(r"[，,：:；;。]", s)]
    switch = "切换至其他角色" in whole or any(
        "离场" in s and any(w in s for w in ("清除", "移除", "消失", "结束", "清空", "失去"))
        for s in related)
    starts = [c for c in clauses
              if "时" in c or c.endswith("后") or any(w in c for w in ("命中", "每次", "每当"))]
    starts = [c for c in starts
              if not any(w in c for w in ("持续", "同时", "时间", "离场", "层时", "秒后"))]
    return {
        "seconds": lasts_for,
        "refresh": any(_starts_often(c) for c in starts),
        "switch": switch,
        "clears": any(w in whole for w in ("清空", "清除")),
        "rate": int(rate.group(2)) / float(rate.group(1) or 1) if rate else None,
        "full_only": int(full.group(1)) if full else None,
    }


def _starts_often(clause: str) -> bool:
    """What starts a buff happens throughout a turn (D315): a skill used again and again, a hit,
    a heal -- not an intro, an outro, 共鸣解放 or an echo's skill, once a turn."""
    if any(w in clause for w in _OFTEN):
        return True
    if any(w in clause for w in _ONCE):
        return False
    return any(w in clause for w in ("命中", "造成伤害", "每次", "每当"))


def _share(effect: dict, said: dict, field: float, typed: bool) -> float:
    """The share of a turn on the field this effect counts for (D315): the share of it that it is
    up, and of stacks that build anew each turn, the average there are -- one a second where the
    words do not say. Stacks nothing ends are full, as they were."""
    if "uptime" in effect:  # read by hand
        return float(effect["uptime"])
    window, up = field, 1.0
    if said["seconds"] and not said["refresh"]:
        window = min(field, said["seconds"])
        up = window / field
    builds = said["switch"] or said["clears"]
    rate = said["rate"] or 1.0
    if said["full_only"]:
        return max(0.0, window - said["full_only"] / rate) / field if builds else up
    stacks = int(effect.get("stacks") or 1)
    if effect.get("per_stack") and not typed and builds and stacks > 1:
        full = stacks / rate
        average = stacks * (1 - full / (2 * window)) if full < window else rate * window / 2
        return up * average / stacks
    return up


def shares(text: str, effects: list[dict], field: float, typed: bool = False) -> list[float]:
    """Each effect's share of a turn of `field` seconds (D315)."""
    return [_share(e, t, field, typed) for e, t in zip(effects, timing(text, effects), strict=True)]


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
        given = copy.deepcopy(_of_mode([given], mode_of(data, name, setup))[0])
        for need in given.get("needs") or []:
            have = float(stats.get(need["stat"]) or 0)
            need.update(have=have, met=have >= need["value"] - 1e-9)
        out.append(given)
    return out


#: A buff's stat that is the enemy's, not the resonator's.
_ENEMY = {"def_ignore", "res_shred"}


def _apply(
    listed: list[dict], toggles: dict, element: int | None = None, tags: set[str] | None = None,
    field: float | None = None,
) -> tuple[dict, dict, list[dict]]:
    """The buffs that are on -- every one listed, unless switched off (D272): what they add to
    the buffs, to the enemy, and the effects for one kind of hit or one skill only. An amplify
    of another element than the resonator's counts for nothing; nor does an effect whose
    condition asks for one the resonator does not apply (D290: `when`, against their `tags`),
    which is marked `unmet` for the page to say."""
    buffs: dict[str, float] = {}
    enemy: dict[str, float] = {}
    scoped: list[dict] = []
    for buff in listed:
        said = toggles.get(buff["id"]) or {}
        if buff.get("always"):
            buff["on"] = True
        else:
            buff["on"] = bool(said["on"]) if "on" in said else not buff.get("off")
        if tags is not None and any(e.get("when") for e in buff["effects"]):
            buff["effects"] = [
                {**e, "unmet": True} if e.get("when") and not set(e["when"]) & tags else e
                for e in buff["effects"]
            ]
        if field and buff["effects"] and not buff.get("always"):
            # counted by the share of a turn on the field it is up (D315)
            parts = shares(buff.get("text") or "", buff["effects"], field,
                           typed=said.get("stacks") is not None)
            buff["effects"] = [{**e, "share": s}
                               for e, s in zip(buff["effects"], parts, strict=True)]
        if not buff["on"] or buff.get("always"):
            continue
        values = said.get("values") or []
        for i, effect in enumerate(buff["effects"]):
            if effect.get("element") and element and effect["element"] != element:
                continue
            # unmet, or given to the others only -- an outro's gift on a weapon (D303)
            if effect.get("unmet") or effect.get("others"):
                continue
            given = values[i] if i < len(values) else None
            value = float(given) if given is not None else effect["value"]
            if effect.get("per_stack"):
                value *= int(said.get("stacks") or effect.get("stacks") or 1)
            if given is None and "share" in effect:
                value *= effect["share"]
            if effect.get("kind") or effect.get("skill") or effect.get("effect"):
                scoped.append({**effect, "value": value})
            elif effect.get("needs") and effect["needs"].get("stat"):
                # it grows with a stat (D296): worked out once the panel without it is known
                buffs.setdefault("_grows", []).append({**effect, "value": value})
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

    # 偏谐值累积效率 is the stat of one who tunes (D311): another has none to start from
    if not set(role.get("tags") or []) & TUNERS:
        out["tune_eff"] = 0.0
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
        # only what its level has unlocked (D302)
        for sub in unlocked_subs(echo):
            if sub.get("stat"):
                add(sub["stat"], sub.get("value") or 0)
    sets = _set_counts(setup.get("echoes") if echoes is None else echoes)
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
        "tune_eff",
        *(f"dmg_{e}" for e in range(1, 7)),
    ):
        add(key, buffs.get(key) or 0)
    # 本属性 by hand: the resonator's own element (D304)
    if role.get("element"):
        add(f"dmg_{role['element']}", buffs.get("dmg_elem") or 0)

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
        # a status effect's own damage: its rows only (D291)
        if effect.get("effect") and effect["effect"] != row.get("effect"):
            continue
        named = effect.get("skill")
        if named and named != skill["name"] and named not in row["name"]:
            continue
        out[effect["stat"]] = out.get(effect["stat"], 0.0) + effect["value"]
    return out


#: The skill the rows buffs bring are listed under (D316).
BORN = {"type": "buff", "name": "增益带来的"}


def _with_born(data: dict, role: dict, name: str, setup: dict, listed: list[dict]) -> dict:
    """The resonator's kit with the rows their buffs bring (D316): a heal over time, an extra
    hit -- of the buffs that are on, and of the gifts they give (白芷's outro heals). A row that
    is a share of another hit (`like`, `share`) takes that hit's multiplier at its level."""
    born = []
    sources = [b for b in listed if b.get("on") and not b.get("always")]
    sources += [g for g in role.get("gives") or [] if _unlocked(g, data, name, setup)]
    for buff in sources:
        for row in buff.get("rows") or []:
            row = {**row, "from": buff["id"]}
            if row.get("like"):
                like = _row_named(role, setup, row["like"])
                if like is None:
                    continue
                said = parse_multiplier(like[1])
                if said is None:
                    continue
                share = float(row.get("share") or 1)
                hits = "+".join(f"{h * share * 100:.2f}%" for h in said["hits"])
                row = {"kind": "damage", "stat": like[0].get("stat") or "atk", **row,
                       "values": [hits]}
            born.append(row)
    if not born:
        return role
    return {**role, "skills": [*(role.get("skills") or []), {**BORN, "rows": born}]}


def _row_named(role: dict, setup: dict, name: str) -> tuple[dict, str] | None:
    """A row of the kit by its name, or the first of a skill by the skill's, with its multiplier
    at the skill's level."""
    for skill in role.get("skills") or []:
        for row in skill["rows"]:
            if row["name"] == name or (skill["name"] == name and row is skill["rows"][0]):
                at = int((setup.get("skills") or {}).get(str(skill["type"]), 10))
                return row, row["values"][min(max(at, 1), len(row["values"])) - 1]
    return None


def _rows(
    data: dict, role: dict, setup: dict, stats: dict, scoped: list[dict] | None = None
) -> list[dict]:
    buffs = setup.get("buffs") or {}
    enemy = setup.get("enemy") or {}
    level = int(setup.get("level", 90))
    # the enemy's own, and what was added by hand (D304)
    ignore = float(enemy.get("def_ignore") or 0) + float(buffs.get("def_ignore") or 0)
    shred = float(enemy.get("res_shred") or 0) + float(buffs.get("res_shred") or 0)
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
                **({"effect": row["effect"]} if row.get("effect") else {}),
                # the buff a row came from (D316)
                **({"from": row["from"]} if row.get("from") else {}),
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
                    * (1 + float(buffs.get("amplify") or 0) + extra.get("amplify", 0)
                       + float(buffs.get(f"amplify_{row.get('bonus')}") or 0))
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
    status = _status_rows(data, role, setup, scoped or [])
    if status:
        out.append(status)
    return out


def _status_rows(data: dict, role: dict, setup: dict, scoped: list[dict]) -> dict | None:
    """A status effect's own damage (D292), for one whose game tags say they apply it, where the
    data has its rates: the level's base times the rate for its stacks (`setup.status`, else the
    most), times DEF and resistance -- no ATK, no crit, as the community's tests found; a raise
    to that effect's own damage counts. Only 光噪's rates are in the game's tables."""
    status = data.get("status") or {}
    tags = set(role.get("tags") or [])
    enemy = setup.get("enemy") or {}
    level = int(setup.get("level", 90))
    base = float((status.get("base") or {}).get(str(level)) or 0)
    rows = []
    for name, rates in (status.get("rates") or {}).items():
        if name not in tags or not rates or not base:
            continue
        stacks = int((setup.get("status") or {}).get(name) or len(rates))
        stacks = min(max(stacks, 1), len(rates))
        row = {"name": f"{name}效应伤害", "bonus": "status", "effect": name}
        extra = _for_row(scoped, {"name": "异常效应"}, row)
        defence = def_mult(
            level,
            int(enemy.get("level", 100)),
            float(enemy.get("def_ignore") or 0) + extra.get("def_ignore", 0),
        )
        resist = res_mult(
            float(enemy.get("res", 0.2)) - float(enemy.get("res_shred") or 0)
            - extra.get("res_shred", 0)
        )
        amount = base * rates[stacks - 1] * (1 + extra.get("amplify", 0)) * defence * resist
        rows.append({
            **row,
            "kind": "damage",
            "multiplier": f"{rates[stacks - 1] * 100:.2f}%",
            "stacks": stacks,
            "max_stacks": len(rates),
            "community": True,
            "noncrit": amount,
            "crit": amount,
            "expected": amount,
        })
    return {"type": "status", "name": "异常效应", "level": level, "rows": rows} if rows else None


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
        listed = _of_mode(available(data, role_name, base), mode_of(data, role_name, base))
        # what they apply, and in a team what the others do (D290, D287)
        # and who they are: a passive may name one resonator (D303)
        tags = set(role.get("tags") or []) | {role_name} | set(setup.get("_team_tags") or [])
        buffs, enemy, scoped = _apply(listed, toggles, role.get("element"), tags,
                                      field_of(data, role_name, base))
        grows = buffs.pop("_grows", [])
        mine = _with_buffs(base, buffs, enemy)
        stats = panel(data, mine)
        kit = _with_born(data, role, role_name, base, listed)
        if grows:
            # a buff that grows with a stat gives what the stat reaches past where it starts, up
            # to its cap (D296): before, each counted at its cap whatever the stat was
            for effect in grows:
                need = effect["needs"]
                start, top = float(need.get("from") or 0), float(need["value"])
                have = float(stats.get(need["stat"]) or 0)
                share = 1.0 if top <= start else min(max((have - start) / (top - start), 0.0), 1.0)
                buffs[effect["stat"]] = buffs.get(effect["stat"], 0.0) + effect["value"] * share
            mine = _with_buffs(base, buffs, enemy)
            stats = panel(data, mine)
        raw = dict(stats)
        for key, value in typed.items():
            # B keeps A's typed number, moved by what B changed (D273)
            stats[key] = value + (stats[key] - worked[key] if worked else 0.0)
        return stats, _rows(data, kit, mine, stats, scoped), listed, mine, raw

    stats, skills, listed, mine, raw = side(setup)
    enemy = mine.get("enemy") or {}
    defence = def_mult(
        int(setup.get("level", 90)),
        int(enemy.get("level", 100)),
        float(enemy.get("def_ignore") or 0)
        + float((mine.get("buffs") or {}).get("def_ignore") or 0),
    )
    said = {
        "panel": stats,
        "typed": sorted(typed),
        "skills": skills,
        "buffs": listed,
        "sets": set_tally(data, setup.get("echoes") or []),
        "compare": None,
        "enemy": {**enemy, "def": defence},
        "gives": gives(data, role_name, setup, stats),
        "round": round_of(data, role_name, stats, mine.get("buffs") or {}),
        "mode": mode_of(data, role_name, setup),
        "kind": kind_of(data, role_name, setup),
        "field": field_of(data, role_name, setup),
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


#: The game's tags for the kind of damage a resonator deals (D277), as the hit's kind.
_DEALS = {"普攻伤害": "basic", "重击伤害": "heavy", "共鸣技能伤害": "skill", "共鸣解放伤害": "lib"}


def _main_kind(role: dict) -> str | None:
    """The kind of damage a resonator deals most (D277): the one the game tags them with
    (爱弥斯 共鸣解放伤害); with no such tag, the kind whose rows multiply most at level 10."""
    for tag in role.get("tags") or []:
        if tag in _DEALS:
            return _DEALS[tag]
    sums: collections.Counter = collections.Counter()
    for skill in role.get("skills") or []:
        for row in skill["rows"]:
            said = parse_multiplier(row["values"][-1]) if row["kind"] == "damage" else None
            if said and row.get("bonus"):
                sums[row["bonus"]] += sum(said["hits"])
    return sums.most_common(1)[0][0] if sums else None


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
    kind = _main_kind(role)
    return [role.get("scales") or "atk", "crit", "crit_dmg"] + ([f"dmg_{kind}"] if kind else [])


def _limits_of(role: dict, setup: dict) -> list[dict]:
    chain = int(setup.get("chain") or 0)
    best: dict[str, float] = {}
    for limit in role.get("limits") or []:
        if int(limit.get("n") or 0) > chain:
            continue
        best[limit["stat"]] = max(best.get(limit["stat"], 0.0), float(limit["value"]))
    return [{"stat": k, "value": v} for k, v in best.items()]


#: The 协奏能量 an outro needs.
OUTRO = 100.0


def round_of(data: dict, name: str, stats: dict, buffs: dict) -> dict | None:
    """How many passes of the kit one round takes (D303): the outro waits on 100 协奏能量, 共鸣解放
    on its cost in 共鸣能量 -- which 共鸣效率 multiplies -- and the round on the slower. A passive's
    协奏能量 or 共鸣能量 comes once a pass. None where the data has no energy (before BUILD 7)."""
    energy = data["roles"][name].get("energy") or {}
    kit, cost = energy.get("kit") or {}, energy.get("cost")
    if not kit or not cost:
        return None
    rate = float(stats.get("er") or 1.0)
    gained = sum(p["energy"] for p in kit.values()) * rate + float(buffs.get("energy") or 0)
    concerto = sum(p["concerto"] for p in kit.values()) + float(buffs.get("concerto") or 0)
    outro = OUTRO / concerto if concerto > 0 else None
    lib = float(cost) / gained if gained > 0 else None
    waits = [p for p in (outro, lib) if p is not None]
    if not waits:
        return None
    return {"energy": gained, "concerto": concerto, "cost": float(cost), "outro": outro,
            "lib": lib, "passes": max(waits)}


#: The one carry every support's gifts are weighed on (D303): a level-90 carry built as most are --
#: base ATK 1000 (resonator and 5★ weapon), 100% ATK and 350 flat from echoes, 90% damage bonus,
#: crit 70% / 220% -- against a level-100 enemy with 10% resistance.
REFERENCE = {"base_atk": 1000.0, "atk_pct": 1.0, "atk": 350.0, "dmg": 0.9, "crit": 0.7,
             "crit_dmg": 2.2, "level": 90, "enemy": 100, "res": 0.1}


def team_gain(effects: list[dict]) -> float:
    """What these gifts raise `REFERENCE`'s damage by, as a factor (D303). ATK and a damage bonus
    add to what the carry has, 加深 and the rest multiply; what only raises the giver -- heals,
    共鸣效率, HP -- raises no one's damage. A status effect's own damage is no hit of the
    carry's."""
    ref = REFERENCE
    sums: dict[str, float] = collections.defaultdict(float)
    for effect in effects:
        if effect.get("unmet") or effect.get("effect"):
            continue
        value = float(effect["value"]) * (int(effect.get("stacks") or 1)
                                          if effect.get("per_stack") else 1)
        stat = effect["stat"]
        sums["dmg" if stat.startswith("dmg_") else stat] += value
    base, flat = ref["base_atk"], ref["atk"]
    atk = (base * (1 + ref["atk_pct"] + sums["atk_pct"]) + flat + sums["atk"]) / (
        base * (1 + ref["atk_pct"]) + flat)
    dmg = (1 + ref["dmg"] + sums["dmg"]) / (1 + ref["dmg"])
    crit = expected_crit(ref["crit"] + sums["crit"], ref["crit_dmg"] + sums["crit_dmg"]) / (
        expected_crit(ref["crit"], ref["crit_dmg"]))
    defence = def_mult(ref["level"], ref["enemy"], sums["def_ignore"]) / def_mult(
        ref["level"], ref["enemy"])
    resist = res_mult(ref["res"] - sums["res_shred"]) / res_mult(ref["res"])
    return (atk * dmg * crit * defence * resist * (1 + sums["amplify"]) * (1 + sums["final"])
            * (1 + sums["mv"]))


def _brought(result: dict) -> list[dict]:
    """What a resonator gives the others with this setup (D303): their own gifts whose needs
    their panel meets, and what their weapon, sets and main echo give the team -- as 配队 gives
    them (D287)."""
    out = []
    for given in result.get("gives") or []:
        if all(need.get("met", True) for need in given.get("needs") or []):
            out += given.get("effects") or []
    for buff in result.get("buffs") or []:
        if buff["source"] in ("weapon", "set", "echo") and buff.get("on", True):
            out += [e for e in buff["effects"]
                    if (e.get("team") or e.get("others")) and not e.get("unmet")]
    return out


def weapon_measure(data: dict, name: str) -> str:
    """What a resonator's weapons are ranked by (D303): a healer's, what they bring each round,
    where the data has their energy; anyone else's, their output (D285)."""
    role = data["roles"][name]
    has_round = bool((role.get("energy") or {}).get("cost"))
    return "brings" if _puts_out(data, name) == "heal" and has_round else "output"


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
    if not any(x["stat"] == "er" for x in lines):
        lines += _round_line(data, name, setup)
    on = _built_on(data, name, setup)
    targets: list[dict] = []
    if not limits or output == "heal":
        mine = compute(data, setup, name, _grade=False)
        theirs = compute(data, best_setup(data, name, setup), name, _grade=False)
        now, best = _output(mine, output), _output(theirs, output)
        capped = {limit["stat"] for limit in limits}
        main = _heal_stat(role) if output == "heal" else role.get("scales") or "atk"
        for stat in on:
            if stat in capped:
                continue
            target = {
                "stat": stat,
                "have": float(mine["panel"].get(stat) or 0),
                "best": float(theirs["panel"].get(stat) or 0),
            }
            if stat == main:
                target.update(_stat_needs(data, name, setup, stat, output, now, best) or {})
            targets.append(target)
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
        "on": on,
        "lines": lines,
        "targets": targets,
        "missing": missing,
    }



def _round_line(data: dict, name: str, setup: dict) -> list[dict]:
    """共鸣效率 enough for one round (D318): 共鸣解放 ready by the time the outro is, so they can
    use it and switch out. The outro waits on 100 协奏能量, which 共鸣效率 does not speed up;
    共鸣解放 on its cost in 共鸣能量, which it multiplies -- a passive's 共鸣能量 each pass as it
    is. None where the data has no energy (before 更新 builds it)."""
    said = compute(data, setup, name, _grade=False)
    turn = said["round"]
    kit = (data["roles"][name].get("energy") or {}).get("kit") or {}
    base = sum(p["energy"] for p in kit.values())
    if not turn or not turn.get("outro") or base <= 0:
        return []
    have = float(said["panel"].get("er") or 1.0)
    passive = turn["energy"] - base * have
    need = max((turn["cost"] / turn["outro"] - passive) / base, 0.0)
    small = round(need * LIMIT_SMALL, 4)
    return [{"stat": "er", "small": small, "need": need, "have": have,
             "met": have >= need - 1e-9, "met_small": have >= small - 1e-9,
             "outro": turn["outro"], "lib": turn["lib"]}]


def _stat_needs(
    data: dict, name: str, setup: dict, stat: str, output: str, now: float, best: float
) -> dict | None:
    """How much of `stat` the panel must reach for 小毕业 and for 大毕业 (D277), the rest as it
    is: what they put out grows in a straight line with the stat it is worked from, so two
    points -- the panel as it is, and the stat typed higher -- give where each line falls."""
    have = float(compute(data, setup, name, _grade=False)["panel"].get(stat) or 0)
    step = max(have, 1000.0)
    typed = {**(setup.get("panel") or {}), stat: have + step}
    higher = _output(compute(data, {**setup, "panel": typed}, name, _grade=False), output)
    slope = (higher - now) / step
    if slope <= 0 or not best:
        return None
    return {
        "small": have + (SMALL * best - now) / slope,
        "need": have + (BIG * best - now) / slope,
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
    capped = {limit["stat"] for limit in _limits_of(role, setup)}
    if kind == "heal":
        return capped | {"er", f"{_heal_stat(role)}_pct"}
    if capped:
        return capped
    scales = role.get("scales") or "atk"
    out = {"crit", "crit_dmg", f"{scales}_pct"}
    kind = _main_kind(role)
    if kind:
        out.add(f"dmg_{kind}")
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
    # the sets: as worn, or each of the game's recommended in full, whichever gives most (D310)
    role = data["roles"][name]
    mode = mode_of(data, name, setup)
    tries = [[e["set"] for e in best["echoes"]]] if any(e["set"] for e in best["echoes"]) else []
    for rec in role.get("recommended") or []:
        if rec.get("mode") in (None, mode) and rec["set"] in (data.get("sets") or {}):
            tries.append(_worn_as(data, rec["set"]))
    if tries:
        def worth(sets: list) -> float:
            trial = copy.deepcopy(best)
            for echo, worn_set in zip(trial["echoes"], sets, strict=True):
                echo["set"] = worn_set
                echo["main"] = echo["main"] or _first_main(data, echo["cost"])
            return _score(data, name, compute(data, trial, name, _grade=False))

        chosen = max(tries, key=worth)
        for echo, worn_set in zip(best["echoes"], chosen, strict=True):
            echo["set"] = worn_set
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


def _first_main(data: dict, cost: int) -> str | None:
    mains = (data["echo"]["main"].get("5") or {}).get(str(cost)) or []
    return mains[0]["stat"] if mains else None


def _worn_as(data: dict, set_name: str) -> list:
    """Five echoes' sets wearing one set as fully as it goes (D310): five of a set of five, three
    of a set of three, the rest none."""
    entry = (data.get("sets") or {}).get(set_name) or {}
    most = max((int(p) for p in (entry.get("text") or {}) if p.isdigit()), default=5)
    return [set_name] * min(most, 5) + [None] * (5 - min(most, 5))


def _score(data: dict, name: str, said: dict) -> float:
    """What a resonator is weighed by (D303): a healer's, what they bring each round where the
    data has it; anyone else's, their output."""
    if weapon_measure(data, name) == "brings":
        return team_gain(_brought(said)) / said["round"]["passes"]
    return _output(said, _puts_out(data, name))


def rank_sets(data: dict, name: str, setup: dict) -> list[dict]:
    """Every set of theirs -- of their element, or of none -- worn as fully as it goes on their
    best build (D310), best first: what 计算 would recommend, beside what the game does."""
    role = data["roles"][name]
    base = best_setup(data, name, {**setup, "echoes": []})

    def weigh(set_name: str, worn: list) -> dict:
        trial = copy.deepcopy(base)
        for echo, worn_set in zip(trial["echoes"], worn, strict=True):
            echo["set"] = worn_set
        return {"set": set_name, "worn": worn,
                "output": _score(data, name, compute(data, trial, name, _grade=False))}

    mine = [n for n, e in (data.get("sets") or {}).items()
            if e.get("element") in (None, role.get("element"))]
    # a set of five first; a smaller one is worn with two of the best of those, as it is in the game
    full = sorted((weigh(n, _worn_as(data, n)) for n in mine if None not in _worn_as(data, n)),
                  key=lambda s: (-s["output"], s["set"]))
    filler = full[0]["set"] if full else None
    bare = weigh("", [None] * 5)["output"]
    for one in full:
        one["adds"] = one["output"] / bare - 1 if bare else 0.0
    out = list(full)
    for n in mine:
        worn = _worn_as(data, n)
        if None in worn:
            one = weigh(n, [s if s is not None else filler for s in worn])
            # what it adds is beside the two pieces it is worn with
            beside = weigh("", [None if s == n else s for s in one["worn"]])["output"]
            one["adds"] = one["output"] / beside - 1 if beside else 0.0
            out.append(one)
    out.sort(key=lambda s: (-s["output"], s["set"]))
    return out


def weapon_stats(data: dict, name: str, level: int = 90, breach: int = 6) -> dict:
    """A weapon's main stat (its ATK) and its secondary stat at a level (D285)."""
    arm = data["weapons"][name]
    curve = data.get("weapon_growth") or {}
    at = (level, breach)
    out = {"atk": arm["atk"] * float(_ratio(curve.get(arm.get("atk_curve"), {}), *at))}
    if arm.get("sub"):
        grow = float(_ratio(curve.get(arm.get("sub_curve"), {}), *at))
        out["sub"] = {"stat": arm["sub"]["stat"], "value": arm["sub"]["value"] * grow}
    return out


def rank_weapons(
    data: dict,
    name: str,
    setup: dict,
    owned: dict[str, int] | None = None,
    only_owned: bool = False,
    signature: str | None = None,
) -> list[dict]:
    """Every weapon this resonator can hold, by what they put out with it (D285), the rest of the
    setup as it is -- each at 90, a 5★ at 精1 and any other at 精5 (bought there cheaply), or at
    the rank held when that is more; with `only_owned`, only those in `owned` (name -> the rank
    held) at that rank. Each with its
    stats at 90, its passive's words at that rank, and its change against the weapon held, at 90
    and its own rank. A panel typed in is left out: it would hide what a weapon changes."""
    role = data["roles"][name]
    owned = owned or {}
    base = copy.deepcopy(setup)
    base.pop("panel", None)
    base.pop("compare", None)
    # five echoes missing: on their best build, where crit is what a built resonator has (D312) --
    # on a bare one, at 5% crit, 暴击伤害 is worth nothing
    built = "setup" if len(base.get("echoes") or []) >= 5 else "best"
    if built == "best":
        base = best_setup(data, name, base)

    def worked(weapon: str, rank: int) -> dict:
        trial = {**base, "weapon": {"name": weapon, "level": 90, "breach": 6, "rank": rank}}
        return compute(data, trial, name, _grade=False)

    def score(said: dict) -> float:
        # a healer: what they bring, by how soon it comes again (D303)
        return _score(data, name, said)

    held = (setup.get("weapon") or {}).get("name")
    weapons = data.get("weapons") or {}
    held_rank = int((setup.get("weapon") or {}).get("rank") or 1)
    now = score(worked(held, held_rank)) if held in weapons else None
    out = []
    for weapon, arm in weapons.items():
        if arm.get("type") != role.get("weapon_type"):
            continue
        if only_owned and weapon not in owned:
            continue
        rarity = int(arm.get("rarity") or 1)
        # in all, a 5★ they already hold above 精1 is at the rank they hold
        mine = max(owned.get(weapon, 0), held_rank if weapon == held else 0)
        rank = owned[weapon] if only_owned else max(1 if rarity >= 5 else 5, mine)
        rank = min(max(int(rank), 1), 5)
        said = worked(weapon, rank)
        got = score(said)
        buffs = arm.get("buffs") or []
        at = buffs[min(rank, len(buffs)) - 1] if buffs else {}
        words = at.get("text") or ""
        # what of it is not counted (D290): a condition they do not meet, and words not read --
        # by hand where it was read by hand (D303)
        mine = next((b for b in said["buffs"] if b["id"] == f"weapon:{weapon}"), None)
        unmet = [e["when"] for e in (mine or {}).get("effects") or [] if e.get("unmet")]
        if arm.get("checked"):
            left = list(at.get("not_counted") or [])
        else:
            left = calc_data.unread(words, at.get("effects") or []) if words else []
        out.append(
            {
                "name": weapon,
                "id": arm.get("id"),
                "rarity": rarity,
                "rank": rank,
                "output": got,
                "change": (got / now - 1) if now else None,
                "current": weapon == held,
                "owned": weapon in owned,
                "owned_rank": owned.get(weapon),
                "signature": weapon == signature,
                "built": built,
                "text": words,
                "unmet": unmet,
                "unread": left,
                "checked": bool(arm.get("checked")),
                "round": said.get("round"),
                "brings": team_gain(_brought(said)),
                "heal": _output(said, "heal"),
                **weapon_stats(data, weapon),
            }
        )
    out.sort(key=lambda w: (-round(w["output"], 9), -w["heal"], -w["rarity"], w["name"]))
    return out


def echo_worth(data: dict, name: str, setup: dict) -> dict:
    """How each echo compares, for the resonator wearing it (D286): what its substats are worth
    -- their output with them against without, as a share -- and each substat alone the same way;
    the weakest of those with substats; and what one more substat at its top roll would add, each
    stat, best first. The set, main stat and cost stay: a piece is compared on what it rolled.
    A panel typed in is left out, as the weapons' ranking leaves it (D285)."""
    kind = _puts_out(data, name)
    base = copy.deepcopy(setup)
    base.pop("panel", None)
    base.pop("compare", None)

    def output(trial: dict) -> float:
        return _output(compute(data, trial, name, _grade=False), kind)

    full = output(base)

    def share(without: float) -> float:
        return full / without - 1 if without else 0.0

    worn = base.get("echoes") or []
    echoes = []
    for i, echo in enumerate(worn):
        subs = echo.get("subs") or []
        bare = copy.deepcopy(base)
        bare["echoes"][i]["subs"] = []
        each = []
        for j in range(len(subs)):
            one = copy.deepcopy(base)
            # its slot left empty, not closed up: a substat past what the level unlocks must
            # not slide into it and be counted (D302)
            one["echoes"][i]["subs"][j] = {"stat": None, "value": 0}
            each.append(share(output(one)))
        echoes.append({"worth": share(output(bare)) if subs else 0.0, "subs": each})
    rolled = [i for i, echo in enumerate(worn) if echo.get("subs")]
    weakest = min(rolled, key=lambda i: echoes[i]["worth"]) if len(rolled) > 1 else None
    rolls = []
    for stat, tiers in SUB_TIERS.items():
        more = copy.deepcopy(base)
        more["buffs"] = {**(more.get("buffs") or {})}
        more["buffs"][stat] = float(more["buffs"].get(stat) or 0) + tiers[-1]
        gain = output(more) / full - 1 if full else 0.0
        rolls.append({"stat": stat, "value": tiers[-1], "gain": gain})
    order = {stat: i for i, stat in enumerate(_SUB_ORDER)}
    rolls.sort(key=lambda r: (-round(r["gain"], 9), order.get(r["stat"], 99)))
    return {"echoes": echoes, "weakest": weakest, "rolls": rolls, "kind": kind}


def _next_of(count: int, rotation: list[dict]) -> dict[int, set[int]]:
    """Who comes on after whom (D287): from the rotation where there is one, each segment the
    next; else the team's order, round."""
    after: dict[int, set[int]] = {i: set() for i in range(count)}
    order = [int(s["member"]) for s in rotation if 0 <= int(s.get("member", -1)) < count]
    if len(order) > 1:
        for a, b in zip(order, order[1:] + order[:1], strict=True):
            if a != b:
                after[a].add(b)
    elif count > 1:
        for i in range(count):
            after[i].add((i + 1) % count)
    return after


def _mine(effect: dict) -> dict:
    """A team effect as the one given it has it."""
    return {k: v for k, v in effect.items() if k not in ("team", "others")}


def team_given(data: dict, members: list[dict], rotation: list[dict]) -> list[list[dict]]:
    """What each member gets from the others (D287), as buffs it can switch off: a resonator's
    gifts to the team (their own words, D272) to everyone else; those to the next one on, to
    whom comes on after them -- or to everyone, when every effect says the whole team; and from
    their weapon, sets and main echo, what is given to the team. A gift whose need the giver's
    panel does not reach (终末回环's 250% 共鸣效率) starts off."""
    after = _next_of(len(members), rotation)
    out: list[list[dict]] = [[] for _ in members]
    for i, giver in enumerate(members):
        name, setup = giver["name"], giver["setup"]
        stats = panel(data, {**setup, "_role": name})
        others = set(range(len(members))) - {i}
        for given in gives(data, name, setup, stats):
            if not given["effects"]:
                continue
            whole = all(e.get("team") for e in given["effects"])
            short = any(not need.get("met", True) for need in given.get("needs") or [])
            for j in others if given["to"] == "team" or whole else after[i]:
                out[j].append(
                    {
                        "id": f"team:{name}:{given['id']}",
                        "source": "team",
                        "from": name,
                        "title": f"{name} · {given['title']}",
                        "text": given["text"],
                        "effects": [_mine(e) for e in given["effects"]],
                        **({"off": True} if short else {}),
                    }
                )
        for buff in available(data, name, setup):
            shared = [e for e in buff["effects"] if e.get("team") or e.get("others")]
            if not shared or buff["source"] not in ("weapon", "set", "echo"):
                continue
            for j in others:
                out[j].append(
                    {
                        "id": f"team:{name}:{buff['id']}",
                        "source": "team",
                        "from": name,
                        "title": f"{name} · {buff['title']}",
                        "text": buff["text"],
                        "effects": [_mine(e) for e in shared],
                    }
                )
    return out


def team(
    data: dict, members: list[dict], rotation: list[dict], toggles: list[dict] | None = None
) -> dict:
    """A team of up to three and a rotation (D287): each member worked out on their own setup with
    what the others give them, then each step of the rotation -- a row of one member's skills,
    so many times -- added up: the team's total and each member's share."""
    given = team_given(data, members, rotation)
    # a condition one member meets for the team: an effect another applies (D290)
    team_tags = sorted({t for m in members for t in data["roles"][m["name"]].get("tags") or []}
                       | {m["name"] for m in members})
    toggles = toggles or [{} for _ in members]
    worked = []
    for i, member in enumerate(members):
        setup = {**member["setup"], "_given": given[i], "_team_tags": team_tags}
        mine = toggles[i] if i < len(toggles) else {}
        setup["toggles"] = {**(member["setup"].get("toggles") or {}), **(mine or {})}
        result = compute(data, setup, member["name"], _grade=False)
        rows = {(str(s["type"]), r["name"]): r for s in result["skills"] for r in s["rows"]}
        worked.append({"name": member["name"], "result": result, "rows": rows,
                       "given": [b for b in result["buffs"] if b["source"] == "team"]})
    segments = []
    totals = [0.0] * len(members)
    heals = [0.0] * len(members)
    for seg in rotation:
        i = int(seg["member"])
        if not 0 <= i < len(members):
            continue
        steps = []
        for step in seg.get("steps") or []:
            row = worked[i]["rows"].get((str(step["skill"]), step["row"]))
            times = float(step.get("times") or 1)
            if not row:
                continue
            amount = (row.get("expected") or 0) * times if row["kind"] == "damage" else 0.0
            healed = (row.get("amount") or 0) * times if row["kind"] == "heal" else 0.0
            totals[i] += amount
            heals[i] += healed
            each = row.get("expected") or row.get("amount") or 0
            said = {"kind": row["kind"], "each": each, "damage": amount, "heal": healed}
            steps.append({**step, **said})
        segments.append({"member": i, "steps": steps, "damage": sum(s["damage"] for s in steps)})
    total = sum(totals)
    return {
        "members": [
            {"name": w["name"], "damage": totals[i], "heal": heals[i],
             "mode": w["result"]["mode"],
             "share": totals[i] / total if total else 0.0, "given": w["given"],
             "skills": w["result"]["skills"], "panel": w["result"]["panel"]}
            for i, w in enumerate(worked)
        ],
        "segments": segments,
        "total": total,
        "heal": sum(heals),
    }


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
    """A 全息's resistance against an element (D273, D281): its base boss's, 10% and 40% in the
    boss's own element as overworld, and where the 全息 raises one, 30% more on top of that --
    the game says only which are raised, so a raise is counted as the overworld boss's own rise."""
    res = 0.1
    if hologram.get("element") and element == hologram["element"]:
        res += 0.3
    if element in (hologram.get("raised") or []):
        res += 0.3
    return round(res, 4)


def _with_change(mine: list[dict], theirs: list[dict]) -> list[dict]:
    """B's rows, each with its change against A's row of the same skill and name (the n-th of
    that name); a row B has alone -- a hit its chain brings (D316) -- is `only_b`, no change."""
    out = copy.deepcopy(theirs)

    def keyed(skills: list[dict]) -> dict:
        seen: dict = collections.Counter()
        found = {}
        for skill in skills:
            for row in skill["rows"]:
                seen[(skill["type"], row["name"])] += 1
                found[(skill["type"], row["name"], seen[(skill["type"], row["name"])])] = row
        return found

    a_rows = keyed(mine)
    for key, b in keyed(out).items():
        a = a_rows.get(key)
        if a is None:
            b.update(change=None, only_b=True)
            continue
        value = "expected" if "expected" in a else "amount"
        b["change"] = (b[value] / a[value] - 1) if a[value] else 0.0
    return out
