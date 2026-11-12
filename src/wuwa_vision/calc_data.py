# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""计算's data (D268): the game's tables, cut to what the calculator reads, as one calc.json.

`tools/fetch_calc.py` fetches the tables from Arikatsu/WutheringWaves_Data (D149) on the
branch of the newest game version, when 更新's button is pressed (D46), and hands them to
`build`. Headless and pure: the tests give it a few rows of each table.

The game's units: a percentage stat is in ten-thousandths (440 = 4.4%), except where a row says
`IsRatio`, which is a plain fraction (0.018 = 1.8%); flat HP, ATK and DEF are as they are.
"""

from __future__ import annotations

import collections
import json
import re
from pathlib import Path

NAME = "calc.json"

#: The tables `build` reads, by the name it gives them, and their paths in the repository.
TABLES: dict[str, str] = {
    "MultiText": "Textmaps/zh-Hans/multi_text/MultiText.json",
    "roleinfo": "BinData/role/roleinfo.json",
    "baseproperty": "BinData/property/baseproperty.json",
    "rolepropertygrowth": "BinData/property/rolepropertygrowth.json",
    "skill": "BinData/skill/skill.json",
    "skilldescription": "BinData/skill/skilldescription.json",
    "damage": "BinData/damage/damage.json",
    "skilltree": "BinData/skillTree/skilltree.json",
    "weaponconf": "BinData/weapon/weaponconf.json",
    "weaponpropertygrowth": "BinData/property/weaponpropertygrowth.json",
    "phantommainproperty": "BinData/phantom/phantommainproperty.json",
    "phantommainpropitem": "BinData/phantom/phantommainpropitem.json",
    "phantomgrowth": "BinData/phantom/phantomgrowth.json",
    "phantomfettergroup": "BinData/phantom/phantomfettergroup.json",
    "phantomfetter": "BinData/phantom/phantomfetter.json",
    "phantomitem": "BinData/phantom/phantomitem.json",
    "resonantchain": "BinData/resonate_chain/resonantchain.json",
    "skillbranch": "BinData/skill/skillbranch.json",
    "phantomskill": "BinData/phantom/phantomskill.json",
    "phantomrecommend": "BinData/VisionRecommend/phantomrecommend.json",
    "phantomplanparam": "BinData/VisionRecommend/phantomplanparam.json",
    "lordgym": "BinData/LordGym/lordgym.json",
    "lordgymentrance": "BinData/LordGym/lordgymentrance.json",
    "lordgymfiltertype": "BinData/LordGym/lordgymfiltertype.json",
    "monsterinfo": "BinData/monster_Info/monsterinfo.json",
    "roletag": "BinData/role/roletag.json",
}

#: The game's stat ids, as the calculator's keys. 10002/10007/10010 are HP/ATK/DEF given on top
#: of the base: a share of it when the row says so, else a flat amount.
PROP: dict[int, str] = {
    2: "hp",
    7: "atk",
    10: "def",
    8: "crit",
    9: "crit_dmg",
    11: "er",
    14: "dmg_skill",
    15: "dmg_all",
    17: "dmg_basic",
    18: "dmg_heavy",
    19: "dmg_lib",
    20: "dmg_intro",
    22: "dmg_1",
    23: "dmg_2",
    24: "dmg_3",
    25: "dmg_4",
    26: "dmg_5",
    27: "dmg_6",
    35: "heal",
    10002: "hp",
    10007: "atk",
    10010: "def",
}
FLAT = {"hp", "atk", "def"}
#: The stat keys in Chinese, for the page.
STATS: dict[str, str] = {
    "hp": "生命",
    "hp_pct": "生命%",
    "atk": "攻击",
    "atk_pct": "攻击%",
    "def": "防御",
    "def_pct": "防御%",
    "crit": "暴击",
    "crit_dmg": "暴击伤害",
    "er": "共鸣效率",
    "heal": "治疗效果加成",
    "dmg_all": "伤害加成",
    "dmg_basic": "普攻伤害加成",
    "dmg_heavy": "重击伤害加成",
    "dmg_skill": "共鸣技能伤害加成",
    "dmg_lib": "共鸣解放伤害加成",
    "dmg_intro": "变奏技能伤害加成",
    "dmg_outro": "延奏技能伤害加成",
    "dmg_1": "冷凝伤害加成",
    "dmg_2": "热熔伤害加成",
    "dmg_3": "导电伤害加成",
    "dmg_4": "气动伤害加成",
    "dmg_5": "衍射伤害加成",
    "dmg_6": "湮灭伤害加成",
}
ELEMENTS = {1: "冷凝", 2: "热熔", 3: "导电", 4: "气动", 5: "衍射", 6: "湮灭"}
#: A hit's kind in the damage table, as the bonus it takes (the research; 5 and the rare kinds
#: are left to the all-damage bonus). Checked by the skills each kind turns up under.
KIND = {0: "basic", 1: "heavy", 2: "lib", 3: "intro", 4: "skill", 7: "outro"}
#: A skill's type: the ones with rows of their own on the page. 4 is the inherent skills,
#: 7 cooking, 12 Tune Break (not yet, D268).
SKILL_TYPES = {
    1: "常态攻击",
    2: "共鸣技能",
    6: "共鸣回路",
    3: "共鸣解放",
    5: "变奏技能",
    11: "延奏技能",
}
RELATED = {7: "atk", 2: "hp", 10: "def"}
#: Every value a substat can roll, lowest to highest (D274). The game's `phantomsubproperty`
#: holds one
#: standard value per stat, not these; they are the published tiers (WutheringInsight's table,
#: christopherklay.github.io/WutheringInsight, and Buffget's for crit and ATK%, which agree).
SUB_TIERS: dict[str, list[float]] = {
    "crit": [0.063, 0.069, 0.075, 0.081, 0.087, 0.093, 0.099, 0.105],
    "crit_dmg": [0.126, 0.138, 0.15, 0.162, 0.174, 0.186, 0.198, 0.21],
    "atk_pct": [0.064, 0.071, 0.079, 0.086, 0.094, 0.101, 0.109, 0.116],
    "hp_pct": [0.064, 0.071, 0.079, 0.086, 0.094, 0.101, 0.109, 0.116],
    "def_pct": [0.081, 0.09, 0.1, 0.109, 0.119, 0.128, 0.138, 0.147],
    "er": [0.068, 0.076, 0.084, 0.092, 0.1, 0.108, 0.116, 0.124],
    **{
        k: [0.064, 0.071, 0.079, 0.086, 0.094, 0.101, 0.109, 0.116]
        for k in ("dmg_basic", "dmg_heavy", "dmg_skill", "dmg_lib")
    },
    "hp": [320, 360, 390, 430, 470, 510, 540, 580],
    "atk": [30, 40, 50, 60],
    "def": [40, 50, 60, 70],
}


def stat(prop: dict | None, *, add_type: int | None = None) -> dict | None:
    """One stat as {stat, value}: `prop` is {Id, Value, IsRatio}, or a row's PropId with its
    value."""
    if not prop:
        return None
    key = PROP.get(int(prop.get("Id") or 0))
    if key is None:
        return None
    value = float(prop.get("Value") or 0)
    ratio = bool(prop.get("IsRatio")) or add_type == 2
    if key in FLAT:
        if not ratio:
            return {"stat": key, "value": value}
        return {"stat": f"{key}_pct", "value": value if prop.get("IsRatio") else value / 10000}
    return {"stat": key, "value": value if prop.get("IsRatio") else value / 10000}


def _text(table: list[dict]) -> dict[str, str]:
    return {row.get("Id"): row.get("Content") or "" for row in table}


def _fill(text: str, params: list[str]) -> str:
    for i, p in enumerate(params):
        text = text.replace("{" + str(i) + "}", p)
    return text


def _kind(name: str) -> str:
    if "治疗" in name or "回复" in name:
        return "heal"
    if "护盾" in name:
        return "shield"
    return "damage"


def build(tables: dict[str, list], version: str) -> dict:
    """calc.json, from the tables in `TABLES` (each a list of rows, as the repository has it)."""
    text = _text(tables.get("MultiText") or [])
    base = {row["Id"]: row for row in tables.get("baseproperty") or [] if row.get("Lv", 1) == 1}
    damage = {row["Id"]: row for row in tables.get("damage") or []}
    rows_by_group: dict[int, list[dict]] = collections.defaultdict(list)
    for row in tables.get("skilldescription") or []:
        rows_by_group[row["SkillLevelGroupId"]].append(row)
    skills_by_role: dict[int, list[dict]] = collections.defaultdict(list)
    for row in tables.get("skill") or []:
        skills_by_role[row["SkillGroupId"]].append(row)
    chains: dict[int, list[dict]] = collections.defaultdict(list)
    for row in tables.get("resonantchain") or []:
        chains[row.get("GroupId")].append(row)
    nodes_by_role = _stat_nodes(tables.get("skilltree") or [], tables.get("skill") or [])
    branches = {row["Id"]: row for row in tables.get("skillbranch") or []}
    tags = {row["Id"]: text.get(row.get("TagName"), "") for row in tables.get("roletag") or []}
    sets = _sets(tables, text)
    set_names = {s["id"]: name for name, s in sets.items()}
    recommended = _recommended(tables, set_names)

    roles: dict[str, dict] = {}
    for role in tables.get("roleinfo") or []:
        if role.get("IsTrial") or role.get("RoleType") != 1:
            continue
        name = text.get(role.get("Name"), "")
        if not name or name.startswith(("dnt", "test")):
            continue
        element = int(role.get("ElementId") or 0)
        if name == "漂泊者":
            name = f"漂泊者·{ELEMENTS.get(element, element)}"
        if name in roles:
            continue
        props = base.get(role.get("PropertyId"))
        if not props:
            continue
        modes = [
            {
                "id": branches[b]["Id"],
                "name": text.get(branches[b].get("Name"), ""),
                "text": _plain(text.get(branches[b].get("Desc"), "")),
            }
            for b in sorted(
                (b for b in role.get("SkillBranchIds") or [] if b in branches),
                key=lambda b: b != role.get("DefaultSkillBranchId"),
            )
        ]
        own_skills = skills_by_role.get(role.get("SkillId"), [])
        own_chain = chains.get(role["Id"], [])
        roles[name] = {
            "id": role["Id"],
            "rarity": role.get("QualityId"),
            "element": element,
            "weapon_type": role.get("WeaponType"),
            "base": {"hp": props.get("LifeMax"), "atk": props.get("Atk"), "def": props.get("Def")},
            "nodes": nodes_by_role.get(role["Id"], []),
            "skills": _skills(
                skills_by_role.get(role.get("SkillId"), []), rows_by_group, damage, text
            ),
            "buffs": _role_buffs(own_skills, own_chain, text, modes),
            "gives": _gives(own_skills, own_chain, text, modes),
            "modes": modes,
            "recommended": recommended.get(role["Id"], []),
            # the game's own tags (主力输出, 生存治疗, ...), the stat its damage grows with, and the
            # stats its words cap (守岸人's 250% 共鸣效率) -- what 毕业 is judged by (D274)
            "tags": [tags[t] for t in role.get("Tag") or [] if tags.get(t)],
            "scales": _scales(own_skills, rows_by_group, damage),
            "limits": _limits(own_skills, own_chain, text),
        }

    growth = {
        f"{row['Level']}/{row['BreachLevel']}": [
            row["LifeMaxRatio"] / 10000,
            row["AtkRatio"] / 10000,
            row["DefRatio"] / 10000,
        ]
        for row in tables.get("rolepropertygrowth") or []
    }
    weapon_growth: dict[str, dict[str, float]] = collections.defaultdict(dict)
    for row in tables.get("weaponpropertygrowth") or []:
        weapon_growth[str(row["CurveId"])][f"{row['Level']}/{row['BreachLevel']}"] = (
            row["CurveValue"] / 10000
        )

    weapons: dict[str, dict] = {}
    for row in tables.get("weaponconf") or []:
        name = text.get(row.get("WeaponName"), "")
        if not name or name in weapons:
            continue
        weapons[name] = {
            "id": row["ItemId"],
            "type": row.get("WeaponType"),
            "rarity": row.get("QualityId"),
            "atk": (row.get("FirstPropId") or {}).get("Value"),
            "atk_curve": str(row.get("FirstCurve")),
            "sub": stat(row.get("SecondPropId")),
            "sub_curve": str(row.get("SecondCurve")),
            "text": _plain(text.get(row.get("Desc"), "")),
            "params": [p.get("ArrayString") or [] for p in row.get("DescParams") or []],
        }
        weapons[name]["buffs"] = [
            {
                "rank": rank,
                "text": _plain(
                    _fill(
                        weapons[name]["text"],
                        [p[min(rank, len(p)) - 1] if p else "" for p in weapons[name]["params"]],
                    )
                ),
                "effects": effects(
                    weapons[name]["text"],
                    [p[min(rank, len(p)) - 1] if p else "" for p in weapons[name]["params"]],
                ),
            }
            for rank in range(1, 6)
        ]

    return {
        "version": version,
        "source": "Arikatsu/WutheringWaves_Data",
        "stats": STATS,
        "elements": {str(k): v for k, v in ELEMENTS.items()},
        "role_growth": growth,
        "weapon_growth": dict(weapon_growth),
        "roles": roles,
        "weapons": weapons,
        "echo": _echo(tables),
        "sets": sets,
        "echoes": _echoes(tables, text, set_names),
        "holograms": _holograms(tables, text),
    }


def _skills(
    skills: list[dict],
    rows_by_group: dict[int, list[dict]],
    damage: dict[int, dict],
    text: dict[str, str],
) -> list[dict]:
    out = []
    for skill in sorted(
        skills,
        key=lambda s: (
            list(SKILL_TYPES).index(s["SkillType"]) if s["SkillType"] in SKILL_TYPES else 99,
            s["Id"],
        ),
    ):
        if skill.get("SkillType") not in SKILL_TYPES:
            continue
        hits = [damage[i] for i in skill.get("DamageList") or [] if i in damage]
        kinds = collections.Counter(KIND.get(h.get("Type"), "other") for h in hits)
        stats = collections.Counter(RELATED.get(h.get("RelatedProperty"), "atk") for h in hits)
        usual = kinds.most_common(1)[0][0] if kinds else "other"
        scales = stats.most_common(1)[0][0] if stats else "atk"
        rows = []
        for row in sorted(
            rows_by_group.get(skill.get("SkillLevelGroupId"), []), key=lambda r: r.get("Order", 0)
        ):
            values = ((row.get("SkillDetailNum") or [{}])[0].get("ArrayString")) or []
            name = text.get(row.get("AttributeName"), "")
            if not name or not any("%" in v for v in values):
                continue
            kind = _kind(name)
            rows.append(
                {
                    "name": name,
                    "kind": kind,
                    "values": values,
                    "stat": "hp" if kind == "heal" and "生命" in name else scales,
                    "bonus": "heavy" if "重击" in name else usual,
                }
            )
        if rows:
            out.append(
                {
                    "type": skill["SkillType"],
                    "name": text.get(skill.get("SkillName"), ""),
                    "rows": rows,
                }
            )
    return out


def _role_buffs(
    skills: list[dict], chain: list[dict], text: dict[str, str], modes: list[dict]
) -> list[dict]:
    """A resonator's inherent skills and chain nodes, each read into effects (D269). An
    inherent skill's `n` is the 共鸣回路 node it comes with; a paragraph for one mode is a
    buff of that mode's (D272)."""
    rows = [
        (
            "inherent",
            s["Id"],
            n,
            text.get(s.get("SkillName"), ""),
            text.get(s.get("SkillDescribe"), ""),
            [str(p) for p in s.get("SkillDetailNum") or []],
        )
        for n, s in enumerate(
            (s for s in sorted(skills, key=lambda s: s["Id"]) if s.get("SkillType") == 4), 1
        )
    ]
    rows += [
        (
            "chain",
            c["GroupIndex"],
            c["GroupIndex"],
            text.get(c.get("NodeName"), ""),
            text.get(c.get("AttributesDescription"), ""),
            [str(p) for p in c.get("AttributesDescriptionParams") or []],
        )
        for c in sorted(chain, key=lambda c: c["GroupIndex"])
    ]
    out = []
    for source, key, n, title, raw, params in rows:
        for mode, part in _by_mode(raw, modes):
            more: dict = {"n": n}
            if mode is not None:
                more["mode"] = mode
            suffix = f":{mode}" if mode is not None else ""
            out.append(_buff(f"{source}:{key}{suffix}", source, title, part, params, **more))
    return out


def _echoes(tables: dict[str, list], text: dict[str, str], set_names: dict[int, str]) -> dict:
    """Every echo once (D269): its cost, and the sets it comes in."""
    cost = {1: 4, 2: 3, 3: 1}
    skills = {row["PhantomSkillId"]: row for row in tables.get("phantomskill") or []}
    out: dict[str, dict] = {}
    for row in tables.get("phantomitem") or []:
        name = text.get(row.get("MonsterName"), "")
        group = int((row.get("MainProp") or {}).get("RandGroupId") or 0)
        if not name or group % 100 not in cost:
            continue
        entry = out.setdefault(
            name, {"id": row.get("MonsterId"), "cost": cost[group % 100], "sets": []}
        )
        element = next((e for e in row.get("ElementType") or [] if e in ELEMENTS), None)
        if element and "element" not in entry:
            entry["element"] = element
        for fetter in row.get("FetterGroup") or []:
            if fetter in set_names and set_names[fetter] not in entry["sets"]:
                entry["sets"].append(set_names[fetter])
        main = _main_buff(skills.get(row.get("SkillId")), text)
        if main and "main_buff" not in entry:
            entry["main_buff"] = main
    return out


def _echo(tables: dict[str, list]) -> dict:
    items = {row["Id"]: row for row in tables.get("phantommainpropitem") or []}
    main: dict[str, dict[str, list]] = collections.defaultdict(
        lambda: collections.defaultdict(list)
    )
    fixed: dict[str, dict[str, dict]] = collections.defaultdict(dict)
    cost = {1: "4", 2: "3", 3: "1"}
    for row in tables.get("phantommainproperty") or []:
        group = int(row["RandGroupId"])
        rarity, slot = str(group // 100), cost.get(group % 100)
        if slot is None:
            continue
        first, *rest = [items[i] for i in row.get("PropGroup") or [] if i in items]
        said = stat(
            {"Id": first["PropId"], "Value": first["StandardProperty"]},
            add_type=first.get("AddType"),
        )
        if said and said not in main[rarity][slot]:
            main[rarity][slot].append(said)
        for other in rest:
            fixed[rarity][slot] = stat(
                {"Id": other["PropId"], "Value": other["StandardProperty"]},
                add_type=other.get("AddType"),
            )
    growth = sorted(
        (row for row in tables.get("phantomgrowth") or [] if row.get("GrowthId") == 1),
        key=lambda r: r["Level"],
    )
    return {
        "main": {k: dict(v) for k, v in main.items()},
        "fixed": dict(fixed),
        "growth": [row["Value"] / 10000 for row in growth],
    }


def _sets(tables: dict[str, list], text: dict[str, str]) -> dict:
    pieces = {row["Id"]: row for row in tables.get("phantomfetter") or []}
    out: dict[str, dict] = {}
    for group in tables.get("phantomfettergroup") or []:
        name = text.get(group.get("FetterGroupName"), "")
        if not name:
            continue
        entry: dict = {"id": group["Id"], "two": [], "text": {}}
        for piece in group.get("FetterMap") or []:
            effect = pieces.get(piece.get("Value"))
            if not effect:
                continue
            count = str(piece.get("Key"))
            # shown as plain words, like a resonator's own (the game's markup taken out)
            entry["text"][count] = _plain(
                _fill(
                    text.get(effect.get("EffectDescription"), ""),
                    effect.get("EffectDescriptionParam") or [],
                )
            )
            if count == "2":
                entry["two"] = [s for s in (stat(p) for p in effect.get("AddProp") or []) if s]
                element = next(
                    (int(s["stat"][4:]) for s in entry["two"] if s["stat"][4:].isdigit()), None
                )
                if element:
                    entry["element"] = element
            else:
                entry.setdefault("buffs", {})[count] = effects(
                    text.get(effect.get("EffectDescription"), ""),
                    effect.get("EffectDescriptionParam") or [],
                )
        if "element" not in entry:
            # its element as the game draws it, when its 2-piece names none (D272)
            drawn = _DRAWN.search(group.get("FetterElementPath") or "")
            entry["element"] = _DRAWN_AS[drawn.group(1)] if drawn else None
        out[name] = entry
    return out


# ---- the game's words, read into effects (D269) ----------------------------------------------

_ANY_TAG = re.compile(r"<[^>]+>")
_NAMED = re.compile(r"<color=Highlight>(.*?)</color>")
_RISE = re.compile(r"(提升|增加|加深|降低|减少)(\d+(?:\.\d+)?)%")
_IGNORE = re.compile(r"忽视[^\d，。]*?(\d+(?:\.\d+)?)%[^，。]*?防御")
_STACKS = re.compile(r"(?:最多|可)叠加(\d+|[一二两三四五六七八九十]+)层")
#: A stat that grows with another to a limit: "每0.2%共鸣效率计算为0.01%暴击提升，上限12.5%".
#: Two ways the game writes it (D274): the stat after the number ("计算为0.25%的伤害提升"), or
#: before it ("使该技能造成伤害的暴击提升0.5%"); each may count only past a threshold ("共鸣效率
#: 大于100%时，每超过1%的共鸣效率…", 莫宁's).
_SCALE = re.compile(
    r"每(?:超过)?(?P<per>\d+(?:\.\d+)?)%的?(?P<by>共鸣效率|攻击|生命|防御)"
    r"(?:计算为(?P<rate>\d+(?:\.\d+)?)%的?(?P<what>[^，。]+?)提升"
    r"|使(?P<what2>[^，。]+?)提升(?P<rate2>\d+(?:\.\d+)?)%)"
    r"，上限(?P<cap>\d+(?:\.\d+)?)%"
)
_OVER = re.compile(r"(共鸣效率|攻击|生命|防御)大于(\d+(?:\.\d+)?)%时[，,]?$")
_NEED = {"共鸣效率": "er", "攻击": "atk", "生命": "hp", "防御": "def"}
#: How the game draws a set's element (`FetterElementPath`).
_DRAWN = re.compile(r"IconElementAttri(Ice|Fire|Thunder|Wind|Light|Dark)")
_DRAWN_AS = {"Ice": 1, "Fire": 2, "Thunder": 3, "Wind": 4, "Light": 5, "Dark": 6}
_NUMERALS = dict(zip("一二两三四五六七八九十", (1, 2, 2, 3, 4, 5, 6, 7, 8, 9, 10), strict=True))
#: The words for a kind of hit, as the bonus it takes.
KIND_WORDS = (
    ("普通攻击", "basic"),
    ("普攻", "basic"),
    ("重击", "heavy"),
    ("共鸣技能", "skill"),
    ("共鸣解放", "lib"),
    ("变奏技能", "intro"),
    ("延奏技能", "outro"),
)


def _plain(text: str) -> str:
    """The game's words without their markup: every tag goes and what it wraps stays -- also
    where one sits inside another (<color>【<te>电磁效应</te>】</color>, D272)."""
    return _ANY_TAG.sub("", text)


def _count(word: str) -> int:
    return int(word) if word.isdigit() else _NUMERALS.get(word, 1)


def _stat_of(subject: str, verb: str) -> str | None:
    """The bucket the words before 提升/加深/降低 name, or None."""
    if "抗性" in subject:
        return "res_shred" if verb in ("降低", "减少") else None
    if verb in ("降低", "减少"):
        return "def_ignore" if "防御" in subject else None
    if "倍率" in subject:
        return "mv"
    if verb == "加深":
        return "amplify"
    if "暴击伤害" in subject:
        return "crit_dmg"
    if "暴击" in subject:
        return "crit"
    if "共鸣效率" in subject:
        return "er"
    if "治疗效果" in subject:
        return "heal"
    if "造成的伤害" in subject:
        return "final"
    for element, name in ELEMENTS.items():
        if f"{name}伤害" in subject:
            return f"dmg_{element}"
    if "伤害" in subject:
        kind = _kind_in(subject)
        return f"dmg_{kind}" if kind else "dmg_all"
    for word, key in (("攻击", "atk_pct"), ("生命", "hp_pct"), ("防御", "def_pct")):
        if word in subject:
            return key
    return None


def _kind_in(text: str) -> str | None:
    return next((kind for word, kind in KIND_WORDS if word in text), None)


def effects(raw: str, params: list[str] | None = None) -> list[dict]:
    """The effects the game's words say: [{stat, value, kind?, skill?, stacks?, per_stack?,
    team?}]. Each clause is a condition (it ends in 时 or 后) or effects; the skill an effect
    is for is the skill named in its clause, or -- when the clause has no subject of its own
    ("造成的伤害提升") -- in the clause before it. What cannot be read is left out."""
    filled = _fill(raw, params or [])
    out: list[dict] = []
    for sentence in re.split(r"[。；;\n]", filled):
        if not sentence.strip():
            continue
        plain = _plain(sentence)
        stacks = _STACKS.search(plain)
        per_stack = bool(stacks) or ("每" in plain and "层" in plain)
        found: list[dict] = []
        scope: dict = {}
        # a stat that grows with another to a limit spans two clauses: read first, then left out
        for scale in _SCALE.finditer(plain):
            what = scale.group("what") or scale.group("what2") or ""
            key, need = _stat_of(what, "提升"), _NEED.get(scale.group("by"))
            if key is None or need is None:
                continue
            per = float(scale.group("per"))
            rate = float(scale.group("rate") or scale.group("rate2"))
            cap = float(scale.group("cap"))
            # counted only past a threshold: the cap needs the threshold too
            over = _OVER.search(plain[: scale.start()])
            base = float(over.group(2)) if over and _NEED.get(over.group(1)) == need else 0.0
            found.append(
                {
                    "stat": key,
                    "value": cap / 100,
                    "needs": {"stat": need, "value": round((base + cap / rate * per) / 100, 6)},
                }
            )
        if found:
            sentence = _SCALE.sub("", plain)
        for clause in re.split(r"[，,]", sentence):
            words = _plain(clause).strip()
            if not words or words.endswith(("时", "后")):
                continue
            named = [_plain(n) for n in _NAMED.findall(clause)]
            ignored = _IGNORE.search(words)
            if ignored:
                found.append({"stat": "def_ignore", "value": float(ignored.group(1)) / 100})
            start = 0
            for rise in _RISE.finditer(words):
                subject = words[start : rise.start()]
                start = rise.end()
                key = _stat_of(subject, rise.group(1))
                if key is None:
                    continue
                own = {
                    "kind": _kind_in(subject) if key in ("final", "mv", "amplify") else None,
                    "skill": named[0] if named else None,
                }
                if not any(own.values()) and subject.lstrip("的").startswith(("造成的", "倍率")):
                    own = dict(scope)
                elif any(own.values()):
                    scope = own
                effect: dict = {"stat": key, "value": float(rise.group(2)) / 100}
                if key == "amplify":
                    element = next((e for e, n in ELEMENTS.items() if f"{n}伤害" in subject), None)
                    if element:
                        effect["element"] = element
                if own.get("kind"):
                    effect["kind"] = own["kind"]
                if own.get("skill"):
                    effect["skill"] = own["skill"]
                if "队伍" in subject:
                    effect["team"] = True
                found.append(effect)
        for effect in found:
            if per_stack:
                effect["per_stack"] = True
                if stacks:
                    effect["stacks"] = _count(stacks.group(1))
        out.extend(found)
    return out


def _buff(id_: str, source: str, title: str, raw: str, params: list[str], **more: object) -> dict:
    return {
        "id": id_,
        "source": source,
        "title": title,
        "text": _plain(_fill(raw, params)),
        "effects": effects(raw, params),
        **more,
    }


def _stat_nodes(tree: list[dict], skills: list[dict]) -> dict[int, list[dict]]:
    """Each resonator's stat nodes (D272): the stat, the skill it sits under (its root in the
    tree, as the detail panel draws it) and how far up it sits."""
    types = {row["Id"]: str(row.get("SkillType")) for row in skills}
    # a node's parents are named by their place in the tree (NodeIndex), not their Id
    by_id = {
        (row.get("NodeGroup"), row.get("NodeIndex", row.get("Id"))): row
        for row in tree
        if "NodeIndex" in row or "Id" in row
    }
    out: dict[int, list[dict]] = collections.defaultdict(list)
    for row in tree:
        if row.get("NodeType") != 4:
            continue
        tier, root, seen = 1, None, 0
        parent = (row.get("ParentNodes") or [None])[0]
        while parent is not None and seen < 10:
            above = by_id.get((row["NodeGroup"], parent))
            if above is None:
                break
            if above.get("NodeType") == 4:
                tier += 1
                parent = (above.get("ParentNodes") or [None])[0]
                seen += 1
                continue
            root = types.get(above.get("SkillId"))
            break
        for prop in row.get("Property") or []:
            said = stat(prop)
            if said:
                if root is not None:
                    said.update(skill=root, tier=tier)
                out[row["NodeGroup"]].append(said)
    return out


def _by_mode(raw: str, modes: list[dict]) -> list[tuple[int | None, str]]:
    """A skill's words, cut where a paragraph says which mode it is for ("处于共鸣模态·电磁时…",
    D272): [(mode id or None, words)]. A paragraph after a mode's stays with it."""
    names = {m["name"]: m["id"] for m in modes if m.get("name")}
    if not names:
        return [(None, raw)]
    out: list[tuple[int | None, list[str]]] = [(None, [])]
    for line in raw.split("\n"):
        plain = _plain(line).lstrip("·-• \t")
        mode = next((i for n, i in names.items() if plain.startswith(f"处于{n}")), None)
        if mode is not None:
            out.append((mode, []))
        out[-1][1].append(line)
    return [(mode, "\n".join(lines).strip()) for mode, lines in out if "".join(lines).strip()]


#: Who a buff is given to (D272): the next resonator only, or the whole team.
_NEXT = re.compile(r"下一[位个名]的?登场的?角色")
_TEAM = ("队伍中的角色", "队伍中所有角色", "队伍中登场角色", "队伍中除", "附近队伍中")
_SECONDS = re.compile(r"持续(\d+(?:\.\d+)?)秒")
#: The skills whose words can give something on: 技能, 解放, 固有, 变奏, 回路, 延奏.
_GIVING = {2: "skill", 3: "skill", 4: "inherent", 5: "skill", 6: "skill", 11: "outro"}


def _to_whom(paragraph: str) -> str | None:
    """'next' or 'team' when a clause that is not a condition names them, else None."""
    for clause in re.split(r"[，,；;。]", paragraph):
        words = clause.strip()
        if not words or words.endswith(("时", "后")):
            continue
        if _NEXT.search(words):
            return "next"
        if any(word in words for word in _TEAM):
            return "team"
    return None


def _gives(
    skills: list[dict], chain: list[dict], text: dict[str, str], modes: list[dict]
) -> list[dict]:
    """What this resonator gives the others (D272), paragraph by paragraph: to whom, whether it
    ends when the one who got it switches out, how long it lasts, and what a limit needs."""
    sources: list[tuple[str, str, str, str, list[str], dict]] = []
    inherent = 0
    for s in sorted(skills, key=lambda s: s["Id"]):
        kind = _GIVING.get(s.get("SkillType"))
        if kind is None:
            continue
        more: dict = {}
        if kind == "inherent":
            inherent += 1
            more["n"] = inherent
        sources.append(
            (
                f"{kind}:{s['Id']}",
                kind,
                text.get(s.get("SkillName"), ""),
                text.get(s.get("SkillDescribe"), ""),
                [str(p) for p in s.get("SkillDetailNum") or []],
                more,
            )
        )
    for c in sorted(chain, key=lambda c: c["GroupIndex"]):
        sources.append(
            (
                f"chain:{c['GroupIndex']}",
                "chain",
                text.get(c.get("NodeName"), ""),
                text.get(c.get("AttributesDescription"), ""),
                [str(p) for p in c.get("AttributesDescriptionParams") or []],
                {"n": c["GroupIndex"]},
            )
        )
    out = []
    for id_, kind, title, raw, params, more in sources:
        count = 0
        for mode, part in _by_mode(raw, modes):
            for paragraph in part.split("\n"):
                plain = _plain(_fill(paragraph, params)).strip()
                to = _to_whom(plain) if plain else None
                if to is None:
                    continue
                said = effects(paragraph, params)
                if not said:
                    continue
                count += 1
                lasts = _SECONDS.search(plain)
                entry = {
                    "id": f"{id_}:{count}",
                    "source": kind,
                    "title": title,
                    "text": plain,
                    "to": to,
                    "ends_on_switch": "切换至其他角色" in plain,
                    "seconds": float(lasts.group(1)) if lasts else None,
                    "effects": said,
                    **more,
                }
                if kind == "outro" and count == 1:
                    entry["id"] = id_
                needs = [e["needs"] for e in said if e.get("needs")]
                if needs:
                    entry["needs"] = needs
                if mode is not None:
                    entry["mode"] = mode
                out.append(entry)
    for entry in out:
        if entry["seconds"] is not None and entry["seconds"].is_integer():
            entry["seconds"] = int(entry["seconds"])
    return out


def _main_buff(skill: dict | None, text: dict[str, str]) -> dict | None:
    """What an echo gives when it is the main echo, in the first slot (D272), at 5★."""
    if not skill:
        return None
    raw = text.get(skill.get("DescriptionEx"), "")
    levels = skill.get("LevelDescStrArray") or []
    params = (levels[-1].get("ArrayString") if levels else None) or []
    for line in raw.split("\n"):
        at = line.find("在首位")
        if at < 0:
            continue
        words = line[at:]
        return {"text": _plain(_fill(words, params)).strip(), "effects": effects(words, params)}
    return None


def _recommended(tables: dict[str, list], set_names: dict[int, str]) -> dict[int, list[dict]]:
    """The game's own recommended sets for each resonator (D272), each with the mode it is
    for where there are modes (`VisionRecommend`)."""
    plans = {row["Id"]: row for row in tables.get("phantomplanparam") or []}
    out: dict[int, list[dict]] = {}
    for row in tables.get("phantomrecommend") or []:
        said = []
        params = row.get("PhantomPlanParamId") or []
        for i, group in enumerate(row.get("RecommendFetterGroups") or []):
            if group not in set_names:
                continue
            plan = plans.get(params[i]) if i < len(params) else None
            mode = (plan or {}).get("SkillBranchId") or None
            said.append({"set": set_names[group], "mode": mode})
        if said:
            out[row["RoleId"]] = said
    return out


def _scales(skills: list[dict], rows_by_group: dict, damage: dict) -> str:
    """The stat most of a resonator's damage grows with (D274): 卡提希娅's is 生命."""
    counts: collections.Counter = collections.Counter()
    for skill in skills:
        for i in skill.get("DamageList") or []:
            if i in damage:
                counts[RELATED.get(damage[i].get("RelatedProperty"), "atk")] += 1
    return counts.most_common(1)[0][0] if counts else "atk"


def _limits(skills: list[dict], chain: list[dict], text: dict[str, str]) -> list[dict]:
    """Every stat a resonator's own words cap (D274): "守岸人自身每0.2%共鸣效率计算为0.01%暴击提升，
    上限12.5%" needs 250% 共鸣效率. A chain's counts from its node."""
    out: list[dict] = []
    rows = [
        (s.get("SkillName"), s.get("SkillDescribe"), s.get("SkillDetailNum"), {}) for s in skills
    ]
    rows += [
        (
            c.get("NodeName"),
            c.get("AttributesDescription"),
            c.get("AttributesDescriptionParams"),
            {"n": c["GroupIndex"]},
        )
        for c in chain
    ]
    for title, raw, params, more in rows:
        for effect in effects(text.get(raw, ""), [str(p) for p in params or []]):
            need = effect.get("needs")
            entry = {**(need or {}), "title": text.get(title, ""), **more}
            if need and entry not in out:
                out.append(entry)
    return out


def _for_player(line: str) -> bool:
    """A 全息 line that gives the player something the calculator can count (D274): about the
    角色 or the 队伍, not the resistance line, not one that only a counter triggers."""
    return (
        ("角色" in line or "队伍" in line)
        and "抗性" not in line
        and not any(w in line for w in ("闪避反击", "逆势回击"))
    )


#: Where the game's 全息战略 groups stand (D273); the others are shown by their name alone.
REGIONS = {"全息战略·强袭": "今州", "全息战略·幻痛": "黎那汐塔"}


def _holograms(tables: dict[str, list], text: dict[str, str]) -> list[dict]:
    """Every 全息战略 boss at difficulty 6 (D273): its name, the game's group, its level, and the
    elements whose resistance the game says it raises (it never says by how much)."""
    gyms = {row["Id"]: row for row in tables.get("lordgym") or [] if not row.get("IsDebug")}
    groups = {
        row["Id"]: text.get(row.get("Name"), "") for row in tables.get("lordgymfiltertype") or []
    }
    monsters = {row["Id"]: text.get(row.get("Name"), "") for row in tables.get("monsterinfo") or []}
    out = []
    for entrance in tables.get("lordgymentrance") or []:
        if entrance.get("IsDebug"):
            continue
        mine = [gyms[i] for i in entrance.get("LordGymList") or [] if i in gyms]
        six = next((g for g in mine if g.get("Difficulty") == 6), None)
        name = monsters.get((six or {}).get("MonsterList", [None])[0]) if six else None
        if not six or not name:
            continue
        words = _plain(text.get(six.get("PlayDescription"), "")).strip()
        line = next((line for line in words.splitlines() if "抗性" in line), "")
        raised = sorted(
            (e for e, n in ELEMENTS.items() if n in line), key=lambda e: line.index(ELEMENTS[e])
        )
        group = groups.get(six.get("FilterType"), "")
        out.append(
            {
                "name": name,
                "group": group,
                "region": REGIONS.get(group),
                "level": int(six.get("MonsterLevel") or 100),
                "raised": raised,
                "text": words,
                # what the fight gives the player, read as buffs (D274): the resistance line is the
                # enemy's, and a lowered DEF here is the player's own, so neither is taken
                "buffs": [
                    e
                    for e in effects("。".join(x for x in words.splitlines() if _for_player(x)))
                    # a reading of 100% or more is a cap ("最多提升100%"), not a step
                    if e["stat"] not in ("def_ignore", "res_shred") and e["value"] < 1.0
                ],
            }
        )
    return out


def load(directory: Path) -> dict | None:
    """calc.json from the catalogue folder, or None when it has not been fetched."""
    try:
        return json.loads((Path(directory) / NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


_CACHE: dict[str, tuple[float, dict | None]] = {}


def cached(directory: Path) -> dict | None:
    """`load`, read again only when the file changed (a fetch on 更新 replaces it)."""
    path = Path(directory) / NAME
    try:
        stamp = path.stat().st_mtime
    except OSError:
        return None
    key = str(path)
    if key not in _CACHE or _CACHE[key][0] != stamp:
        _CACHE[key] = (stamp, load(directory))
    return _CACHE[key][1]
