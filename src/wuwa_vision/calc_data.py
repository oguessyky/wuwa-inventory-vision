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
import hashlib
import json
import re
from pathlib import Path

NAME = "calc.json"
#: What `build` makes, by number (D280): 更新 makes calc.json again when its builder is older,
#: though the game version is the same. 2: each row's stat read from its own kind of hits.
BUILD = 7


def up_to_date(have: dict | None, version: str) -> bool:
    """Whether a calc.json is of this game version and from this builder (D280)."""
    return bool(have) and have.get("version") == version and int(have.get("build") or 0) >= BUILD

#: The tables `build` reads, by the name it gives them, and their paths in the repository.
TABLES: dict[str, str] = {
    "MultiText": "Textmaps/zh-Hans/multi_text/MultiText.json",
    "roleinfo": "BinData/role/roleinfo.json",
    "baseproperty": "BinData/property/baseproperty.json",
    "rolepropertygrowth": "BinData/property/rolepropertygrowth.json",
    "skill": "BinData/skill/skill.json",
    "skilldescription": "BinData/skill/skilldescription.json",
    "damage": "BinData/damage/damage.json",
    "abnormal": "BinData/AbnormalDamage/abnormaldamageconfig.json",
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
    # how fast a resonator builds 偏谐值, 100% to start (D296)
    "tune_eff": "偏谐值累积效率",
    # an echo's own skill's damage (D290, D298): read, and named
    "dmg_echo": "声骸技能伤害加成",
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
            "energy": _energy(own_skills, rows_by_group, damage, text),
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
        "build": BUILD,
        "status": _status(tables),
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


#: A heal's flat part per 1% of its stat (D277): HP heals carry 200 and more (守岸人 1313+5.97%,
#: 莉莉 351+0.70%), ATK heals 40 and less (维里奈 1188+29.75%) -- HP is some ten times ATK.
HP_FLAT_PER_PCT = 100.0
_NUMBER = re.compile(r"(\d+(?:\.\d+)?)(%?)")


#: The damage table's `CalculateType` for each kind of row (D280).
CALCULATE = {"damage": 0, "heal": 1, "shield": 2}


def _most_stat(hits: list[dict]) -> str | None:
    """The stat most of these hits grow with (`RelatedProperty`), or None for no hits."""
    stats = collections.Counter(RELATED.get(h.get("RelatedProperty"), "atk") for h in hits)
    return stats.most_common(1)[0][0] if stats else None


def heal_stat(values: list[str], usual: str) -> str:
    """The stat a heal row is worked from (D277), when its name does not say 生命: HP when its
    flat part is sized for HP, else the stat the skill's damage is worked from."""
    if not values:
        return usual
    pct = flat = 0.0
    for number, percent in _NUMBER.findall(values[-1]):
        if percent:
            pct += float(number)
        else:
            flat += float(number)
    return "hp" if pct and flat / pct >= HP_FLAT_PER_PCT else usual


def _heal_rows_read(data: dict) -> dict:
    """A calc.json from before D280 has its heal rows read again by D277's rule, until 更新
    makes it again (`up_to_date`); one from this builder read each row from the table."""
    if int(data.get("build") or 0) >= 2:
        return data
    for role in (data.get("roles") or {}).values():
        for skill in role.get("skills") or []:
            for row in skill.get("rows") or []:
                if row.get("kind") == "heal" and "生命" not in row.get("name", ""):
                    row["stat"] = heal_stat(row.get("values") or [], row.get("stat") or "atk")
    return data


def _status(tables: dict[str, list]) -> dict:
    """The status effects' own damage (D292): the base for each level (the game's table has one
    column per effect; they are the same), and each effect's rate by stacks where the damage
    table has them -- entries of that effect's `SubType`, one per stack count."""
    base = {}
    for row in tables.get("abnormal") or []:
        values = [v for k, v in row.items() if k.startswith("Abnormal")]
        if values:
            base[str(row["Level"])] = max(values)
    by: dict[str, list[tuple[int, float]]] = collections.defaultdict(list)
    for hit in tables.get("damage") or []:
        sub = (hit.get("SubType") or [None])[0]
        rate = (hit.get("RateLv") or [0])[0]
        if hit.get("Type") == 10 and sub in STATUS_OF and rate and not hit.get("FormulaType"):
            by[STATUS_OF[sub]].append((hit["Id"], rate / 10000))
    return {"base": base, "rates": {k: [r for _, r in sorted(v)] for k, v in by.items()}}


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
        # each row's stat from its skill's hits of its own kind (D280): damage, heal or shield
        of_kind = {k: [h for h in hits if int(h.get("CalculateType") or 0) == n]
                   for k, n in CALCULATE.items()}
        kinds = collections.Counter(
            KIND.get(h.get("Type"), "other") for h in of_kind["damage"] or hits
        )
        usual = kinds.most_common(1)[0][0] if kinds else "other"
        scales = _most_stat(of_kind["damage"] or hits) or "atk"
        # a status effect's damage (D291): most of its damage hits tagged with one
        tagged = collections.Counter(
            STATUS_OF[s] for h in of_kind["damage"] for s in (h.get("SubType") or [])[:1]
            if s in STATUS_OF
        )
        status = tagged.most_common(1)[0][0] if tagged else None
        if status and tagged[status] * 2 <= len(of_kind["damage"]):
            status = None
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
                    "stat": _most_stat(of_kind[kind])
                    or (heal_stat(values, scales) if kind == "heal" else scales),
                    "bonus": "heavy" if "重击" in name else usual,
                    **({"effect": status} if status and kind == "damage" else {}),
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


#: A basic attack done some other way than its chain on the ground: not more of one round (D303).
_ASIDE = ("空中", "闪避", "下落", "冲刺", "跳跃")


def _energy(
    skills: list[dict],
    rows_by_group: dict[int, list[dict]],
    damage: dict[int, dict],
    text: dict[str, str],
) -> dict:
    """What one pass of the kit gives (D303): each part's 共鸣能量 from its hits (the damage
    table's `Energy`, in hundredths) and 协奏能量 as its own rows say -- else from its hits'
    `ElementPower` -- and 共鸣解放's cost. A hit is paired with its row by order where the counts
    agree, so "46.68%*2" counts twice and a basic attack's air and dodge rows are left out."""
    kit: dict[str, dict] = {}
    cost = None
    for skill in skills:
        kind = skill.get("SkillType")
        if kind not in SKILL_TYPES or kind == 11:
            continue
        rows = sorted(rows_by_group.get(skill.get("SkillLevelGroupId"), []),
                      key=lambda r: r.get("Order", 0))
        named = [(text.get(r.get("AttributeName"), ""),
                  (((r.get("SkillDetailNum") or [{}])[0].get("ArrayString")) or [""])[-1])
                 for r in rows]
        hits = [damage[i] for i in skill.get("DamageList") or [] if i in damage
                and int(damage[i].get("CalculateType") or 0) == 0]
        said = [(n, v) for n, v in named if "%" in v and _kind(n) == "damage"]
        if len(said) == len(hits):
            paired = [(h, n, max(len(parse_hits(v) or [0]), 1))
                      for h, (n, v) in zip(hits, said, strict=True)]
        else:
            paired = [(h, "", 1) for h in hits]
        paired = [(h, times) for h, n, times in paired if not n.startswith(_ASIDE)]
        energy = sum((h.get("Energy") or [0])[-1] / 100 * times for h, times in paired)
        rows_say = [float(v) for n, v in named
                    if n.endswith("回复协奏能量") and "额外" not in n and _is_number(v)]
        concerto = (sum(rows_say) if rows_say
                    else sum((h.get("ElementPower") or [0])[-1] / 100 * t for h, t in paired))
        for n, v in named:
            if n.endswith("消耗共鸣能量") and _is_number(v) and cost is None:
                cost = float(v)
        part = kit.setdefault(str(kind), {"energy": 0.0, "concerto": 0.0})
        part["energy"] += energy
        part["concerto"] += concerto
    return {"cost": cost, "kit": kit}


def _is_number(value: str) -> bool:
    try:
        float(value)
    except ValueError:
        return False
    return True


def parse_hits(value: str) -> list[float] | None:
    """The hits a multiplier is ("46.68%*2" two), or None when it is no multiplier."""
    hits: list[float] = []
    for term in value.split("+"):
        match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)%(?:\s*\*\s*(\d+))?\s*", term)
        if match:
            hits += [float(match.group(1)) / 100] * int(match.group(2) or 1)
    return hits or None


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
_RISE = re.compile(r"(提升|提高|增加|加深|降低|减少)(\d+(?:\.\d+)?)%")
#: A hit named in the words that is no kind of its own: the dodge counter is a 普攻 row (D290).
_NAMED_HITS = ("闪避反击",)
#: The stats a kind of hit can take alone ("重击伤害的暴击提升12%", D290).
_KIND_SCOPED = ("final", "mv", "amplify", "crit", "crit_dmg")
_IGNORE = re.compile(r"忽视[^\d，。]*?(\d+(?:\.\d+)?)%[^，。]*?防御")
#: Defence or a resistance ignored, as the game mostly writes it (D290):
#: "共鸣解放伤害无视目标32%防御",
#: "无视目标10%热熔抗性", "无视对方20%的防御"; and lowered: "降低对方16%的气动抗性".
_IGNORES = re.compile(
    r"(?P<verb>无视|降低|减少)(?:目标|对方)的?(?P<value>\d+(?:\.\d+)?)%的?"
    r"(?P<what>防御|(?P<element>冷凝|热熔|导电|气动|衍射|湮灭)?(?:属性)?抗性)"
)
#: A number written before its stat (D290): a main echo's "自身获得12.00%热熔伤害加成提升", or a
#: clause that is only "12.00%普攻伤害加成提升"; "获得48%声骸技能伤害加成".
#: What a condition asks the wielder to apply, as the game's tags for a resonator say they do
#: (D290): "附加霜渐效应后" needs 霜渐; "附加【震谐·偏移】或【集谐·偏移】时" either 偏移;
#: 异常效应 any.
_APPLIES = {
    "霜渐效应": "霜渐", "光噪效应": "光噪", "风蚀效应": "风蚀", "电磁效应": "电磁",
    "虚湮效应": "虚湮", "聚爆效应": "聚爆", "震谐·偏移": "震谐响应", "集谐·偏移": "集谐响应",
}
_ANY_EFFECT = ("霜渐", "光噪", "风蚀", "电磁", "虚湮", "聚爆")


def condition_needs(words: str) -> list[str]:
    """The tags a condition asks for, any one of them; none when it asks for no effect."""
    needs = {tag for word, tag in _APPLIES.items() if word in words}
    if "异常效应" in words:
        needs |= set(_ANY_EFFECT)
    return sorted(needs)


#: The status effects by the damage table's `SubType` (D291): a hit tagged with one is its damage.
STATUS_OF = {1001: "风蚀", 1002: "电磁", 1003: "霜渐", 1004: "聚爆", 1005: "光噪", 1006: "虚湮",
             1007: "霜渐"}


def _status_in(words: str) -> str | None:
    """The status effect whose damage the words name: "【光噪效应】伤害" -> 光噪."""
    return next((s for s in dict.fromkeys(STATUS_OF.values()) if f"{s}效应" in words), None)


#: A stacking effect's cap, written after it: "最多提升24%", "最多无视目标30%防御" (D290).
_CAP = re.compile(r"最多(?P<verb>提升|无视)(?:目标)?的?(?P<value>\d+(?:\.\d+)?)%")
_FIRST = re.compile(
    r"(?:获得|^)(?P<value>\d+(?:\.\d+)?)%的?(?P<what>[^，。%\d]+?)(?:提升)?$"
)
_STACKS = re.compile(r"(?:最多|可)叠加(\d+|[一二两三四五六七八九十]+)层")
#: A stat that grows with another to a limit: "每0.2%共鸣效率计算为0.01%暴击提升，上限12.5%".
#: Two ways the game writes it (D274): the stat after the number ("计算为0.25%的伤害提升"), or
#: before it ("使该技能造成伤害的暴击提升0.5%"); each may count only past a threshold ("共鸣效率
#: 大于100%时，每超过1%的共鸣效率…", 莫宁's).
_SCALE = re.compile(
    r"每(?:超过)?(?P<per>\d+(?:\.\d+)?)%的?(?P<by>共鸣效率|偏谐值累积效率|攻击|生命|防御)"
    r"(?:计算为(?P<rate>\d+(?:\.\d+)?)%的?(?P<what>[^，。]+?)提升"
    r"|使(?P<what2>[^，。]+?)提升(?P<rate2>\d+(?:\.\d+)?)%)"
    r"，上限(?P<cap>\d+(?:\.\d+)?)%"
)
_OVER = re.compile(
    r"(共鸣效率|偏谐值累积效率|攻击|生命|防御)(?:大于|超过)(\d+(?:\.\d+)?)%时[，,]?$"
)
_NEED = {"共鸣效率": "er", "偏谐值累积效率": "tune_eff", "攻击": "atk", "生命": "hp", "防御": "def"}
#: How the game draws a set's element (`FetterElementPath`).
_DRAWN = re.compile(r"IconElementAttri(Ice|Fire|Thunder|Wind|Light|Dark)")
_DRAWN_AS = {"Ice": 1, "Fire": 2, "Thunder": 3, "Wind": 4, "Light": 5, "Dark": 6}
_NUMERALS = dict(zip("一二两三四五六七八九十", (1, 2, 2, 3, 4, 5, 6, 7, 8, 9, 10), strict=True))
#: The words for a kind of hit, as the bonus it takes.
KIND_WORDS = (
    # an echo's own skill: no hit of a resonator's is one (D290)
    ("声骸技能", "echo"),
    ("普通攻击", "basic"),
    ("普攻", "basic"),
    ("重击", "heavy"),
    ("共鸣技能", "skill"),
    ("共鸣解放", "lib"),
    ("变奏技能", "intro"),
    ("延奏技能", "outro"),
)


#: A heal over time (D316): "每3秒回复漂泊者20%攻击的生命值，持续30秒".
_HEAL_OVER_TIME = re.compile(
    r"每(\d+(?:\.\d+)?)秒回复[^，。；%]{0,12}?(\d+(?:\.\d+)?)%(攻击|生命上限|生命|防御)的生命值"
    r"[^。]*?持续(\d+(?:\.\d+)?)秒")
#: An extra hit of its own number (D316): "造成卡卡罗100.00%攻击的导电伤害", "造成凌阳200%攻击的…",
#: "造成吟霖攻击力419.59%的…", "造成220%的气动伤害".
_EXTRA_HIT = re.compile(
    r"造成[^，。；%]{0,8}?(?:(\d+(?:\.\d+)?)%(?:的)?(攻击|生命|防御)?|(攻击|生命|防御)力?"
    r"(\d+(?:\.\d+)?)%)的?[^，。；%]{0,4}?伤害")
_COUNTS_AS = re.compile(
    r"(?:此次伤害为|本次伤害为|该次伤害为|伤害为|伤害视为|该伤害视为|视为)([^，。；]{2,6}?)伤害")
#: Words between 造成 and the number that make it no hit of its own: a share of a skill's
#: (造成共鸣回路一日花100%的…), or no hit at all (造成伤害无视目标10%…).
_NOT_A_HIT = ("伤害", "无视", "提升", "共鸣回路", *(w for w, _ in KIND_WORDS))
_SCALES = {"攻击": "atk", "生命": "hp", "生命上限": "hp", "防御": "def"}


def rows_of(text: str, title: str) -> list[dict]:
    """The rows a buff's words bring (D316): a heal over time as its ticks (每3秒…持续30秒: ten),
    an extra hit of its own number as one row of the damage it counts as (此次伤害为共鸣解放伤害).
    A hit that is a share of another (伤害为…的150%) has no number of its own: read by hand."""
    plain = _plain(text or "")
    out: list[dict] = []
    for heal in _HEAL_OVER_TIME.finditer(plain):
        every, value, scale, lasts = heal.groups()
        ticks = int(float(lasts) // float(every))
        out.append({"name": f"{title}·持续治疗", "kind": "heal", "stat": _SCALES[scale],
                    "values": [f"{float(value):.2f}%*{ticks}"]})
    hits = 0
    sentences = [s for s in re.split(r"(?<=[。；\n])", plain) if s.strip()]
    for i, sentence in enumerate(sentences):
        # "…造成弗洛洛攻击216.42%的湮灭伤害，命中目标时获得8层余响。本次伤害为声骸技能伤害。"
        after = sentences[i + 1].strip() if i + 1 < len(sentences) else ""
        if after.startswith(("此次", "本次", "该次", "该伤害")):
            sentence += after
        hit = _EXTRA_HIT.search(sentence)
        if not hit or "回复" in sentence[: hit.start()].split("，")[-1]:
            continue
        before = hit.group(0)[2: hit.group(0).find(hit.group(1) or hit.group(3))]
        if any(w in before for w in _NOT_A_HIT):
            continue
        hits += 1
        value = hit.group(1) or hit.group(4)
        scale = hit.group(2) or hit.group(3) or "攻击"
        row = {"name": f"{title}·额外伤害{hits if hits > 1 else ''}", "kind": "damage",
               "stat": _SCALES[scale],
               "values": [f"{float(value):.2f}%"]}
        said = _COUNTS_AS.search(sentence)
        kind = next((k for w, k in KIND_WORDS if said and w in said.group(1)), None)
        if kind:
            row["bonus"] = kind
        out.append(row)
    return out


def _plain(text: str) -> str:
    """The game's words without their markup: every tag goes and what it wraps stays -- also
    where one sits inside another (<color>【<te>电磁效应</te>】</color>, D272)."""
    return _ANY_TAG.sub("", text)


def _count(word: str) -> int:
    return int(word) if word.isdigit() else _NUMERALS.get(word, 1)


#: A status effect's own damage (霜渐效应伤害, 【光噪效应】伤害): no row is one (D285).
_EFFECT_DAMAGE = re.compile(r"效应】?的?伤害")


def _stat_of(subject: str, verb: str) -> str | None:
    """The bucket the words before 提升/加深/降低 name, or None."""
    if _EFFECT_DAMAGE.search(subject):
        return None
    if "偏谐值累积效率" in subject:
        return "tune_eff"           # D296
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
    last: list[dict] = []
    for sentence in re.split(r"[。；;\n]", filled):
        if not sentence.strip():
            continue
        plain = _plain(sentence)
        stacks = _STACKS.search(plain)
        per_stack = bool(stacks) or ("每" in plain and "层" in plain)
        found: list[dict] = []
        scope: dict = {}
        # what a condition in this sentence asks the wielder to apply, and from which effect on
        # it holds (D290): "附加霜渐效应后，自身冷凝伤害加成提升30%"
        needs: list[str] = []
        held_from = 0
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
            # where it starts counting kept apart (D296): the stat's own threshold, if any
            grows: dict = {
                "stat": key,
                "value": cap / 100,
                "needs": {"stat": need, "value": round((base + cap / rate * per) / 100, 6),
                          "from": round(base / 100, 6)},
            }
            if "队伍" in what:
                grows["team"] = True
            found.append(grows)
        if found:
            sentence = _SCALE.sub("", plain)
        for clause in re.split(r"[，,]", sentence):
            words = _plain(clause).strip()
            if words.endswith(("时", "后")):
                asked = condition_needs(words)
                if asked and not needs:
                    needs, held_from = asked, len(found)
                continue
            if not words:
                continue
            named = [_plain(n) for n in _NAMED.findall(clause)]
            ignored = _IGNORE.search(words)
            if ignored:
                found.append({"stat": "def_ignore", "value": float(ignored.group(1)) / 100})
            for ignore in _IGNORES.finditer(words):
                # whose hits: a kind ("共鸣解放伤害无视…"), an element ("气动伤害无视…"), or all
                before = words[: ignore.start()]
                if before.endswith("最多"):
                    continue          # "最多无视目标30%防御": the cap of the one before it
                effect = {
                    "stat": "def_ignore" if ignore.group("what") == "防御" else "res_shred",
                    "value": float(ignore.group("value")) / 100,
                }
                kind = _kind_in(before) if "伤害" in before else None
                if kind:
                    effect["kind"] = kind
                element = ignore.group("element") or next(
                    (n for n in ELEMENTS.values() if f"{n}伤害" in before), None
                )
                if element:
                    effect["element"] = next(e for e, n in ELEMENTS.items() if n == element)
                found.append(effect)
            first = _FIRST.search(words) if "造成" not in words else None
            if first and not _RISE.search(words):
                key = _stat_of(first.group("what"), "提升")
                if key is not None:
                    effect = {"stat": key, "value": float(first.group("value")) / 100}
                    if "队伍" in words[: first.start()]:
                        effect["team"] = True
                    found.append(effect)
            start = 0
            for rise in _RISE.finditer(words):
                subject = words[start : rise.start()]
                start = rise.end()
                # a status effect's own damage raised: for the hits that are it (D291)
                status = _status_in(subject) if _EFFECT_DAMAGE.search(subject) else None
                if status and rise.group(1) in ("加深", "提升", "提高", "增加"):
                    effect = {"stat": "amplify", "value": float(rise.group(2)) / 100,
                              "effect": status}
                    if "队伍" in subject:
                        effect["team"] = True
                    found.append(effect)
                    continue
                key = _stat_of(subject, rise.group(1))
                if key is None:
                    continue
                own = {
                    "kind": _kind_in(subject) if key in _KIND_SCOPED and "伤害" in subject
                    or key in ("final", "mv", "amplify") else None,
                    "skill": named[0] if named
                    else next((hit for hit in _NAMED_HITS if hit in subject), None),
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
        for effect in found[held_from:] if needs else []:
            effect["when"] = needs
        # "…普攻伤害加成提升12%。该效果可叠加3层": the stacks of the sentence before (D290)
        if not found and stacks and plain.strip().startswith(("该效果", "可叠加", "最多叠加")):
            for effect in last:
                effect.update(per_stack=True, stacks=_count(stacks.group(1)))
        # "暴击伤害提升4%，最多提升24%", "每消耗1层…无视目标15%防御，最多无视目标30%防御": the cap
        # says how many stacks the one before it takes (D290)
        for cap in _CAP.finditer(plain):
            ignores = cap.group("verb") == "无视"
            said = [e for e in found if (e["stat"] == "def_ignore") == ignores and e["value"] > 0]
            if said:
                top, effect = float(cap.group("value")) / 100, said[-1]
                times = round(top / effect["value"])
                if times >= 2 and abs(times * effect["value"] - top) < 1e-6:
                    effect.update(per_stack=True, stacks=times)
        out.extend(found)
        if found:
            last = found
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
    """The stat most of a resonator's damage grows with (D274): 卡提希娅's is 生命. Their damage
    alone (D280): 莫宁's DEF heals do not make her hits DEF."""
    hits = [damage[i] for s in skills for i in s.get("DamageList") or [] if i in damage]
    dealt = [h for h in hits if int(h.get("CalculateType") or 0) == CALCULATE["damage"]]
    return _most_stat(dealt or hits) or "atk"


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


def _effect_damage_dropped(data: dict) -> dict:
    """A calc.json from before D285 counted a status effect's own damage (灼霜's 霜渐效应伤害加深
    20%, 达妮娅's 聚爆效应伤害加深60%) as all damage: until 更新 makes it again, an unscoped 加深
    that the words give only to such damage is left out -- of weapons, resonators' own buffs and
    what they give, and sets."""
    if int(data.get("build") or 0) >= 3:
        return data

    def keep(text: str, found: list[dict]) -> list[dict]:
        if not _EFFECT_DAMAGE.search(text):
            return found
        read = effects(text)
        said = {(e["stat"], round(e["value"], 6)) for e in read if not e.get("effect")}
        # since D291 such a raise is read for the status effect's own hits: that one instead
        scoped = {round(e["value"], 6): e for e in read if e.get("effect")}
        out = []
        for e in found:
            unscoped = (e["stat"] == "amplify" and not e.get("kind") and not e.get("skill")
                        and not e.get("element") and not e.get("effect"))
            if not unscoped or (e["stat"], round(e["value"], 6)) in said:
                out.append(e)
            elif round(e["value"], 6) in scoped:
                out.append({**e, "effect": scoped[round(e["value"], 6)]["effect"]})
        return out

    for arm in (data.get("weapons") or {}).values():
        for rank in arm.get("buffs") or []:
            rank["effects"] = keep(rank.get("text") or "", rank.get("effects") or [])
    for role in (data.get("roles") or {}).values():
        for buff in [*(role.get("buffs") or []), *(role.get("gives") or [])]:
            buff["effects"] = keep(_plain(buff.get("text") or ""), buff.get("effects") or [])
    for entry in (data.get("sets") or {}).values():
        for pieces, found in (entry.get("buffs") or {}).items():
            words = _plain((entry.get("text") or {}).get(pieces) or "")
            entry["buffs"][pieces] = keep(words, found)
    return data


_PERCENT = re.compile(r"(\d+(?:\.\d+)?)%")


def unread(text: str, said: list[dict]) -> list[str]:
    """The parts of a passive's words with a number the reading did not count (D290): each
    clause, as written, so the page can say what is left out -- a status effect's own damage, a
    heal on hit, a cap no stack explains."""
    counted = set()
    for effect in said:
        counted.add(round(effect["value"] * 100, 3))
        if effect.get("stacks"):
            counted.add(round(effect["value"] * effect["stacks"] * 100, 3))
    out = []
    for clause in re.split(r"[，。；;\n]", _plain(text)):
        words = clause.strip()
        if not words or words.endswith(("时", "后")):
            continue
        numbers = [round(float(n), 3) for n in _PERCENT.findall(words)]
        if numbers and any(n not in counted for n in numbers):
            out.append(words)
    return out


def _words_read_again(data: dict) -> dict:
    """A calc.json from before D290 missed defence and resistance ignored as the game writes it
    (无视目标32%防御, 无视目标10%热熔抗性), a number before its stat (a main echo's
    自身获得12%热熔伤害加成提升) and an echo skill's own damage (it read as all damage). Until
    更新 makes it again, the
    words of weapons, main echoes and sets -- kept as plain text, with nothing a reading loses --
    are read again. A resonator's own words lose the skill they name when kept plain: they stay."""
    if int(data.get("build") or 0) >= 6:
        return data
    for arm in (data.get("weapons") or {}).values():
        for rank in arm.get("buffs") or []:
            if rank.get("text"):
                rank["effects"] = effects(rank["text"])
    for echo in (data.get("echoes") or {}).values():
        main = echo.get("main_buff")
        if main and main.get("text"):
            main["effects"] = effects(main["text"])
    for entry in (data.get("sets") or {}).values():
        for pieces in list(entry.get("buffs") or {}):
            words = (entry.get("text") or {}).get(pieces)
            if words:
                entry["buffs"][pieces] = effects(words)
    return data


#: The passives read by hand (D303), each with the words it was read from; shipped with the app.
JUDGED_PATH = Path(__file__).with_name("calc_judged.json")
JUDGED: dict = json.loads(JUDGED_PATH.read_text(encoding="utf-8"))


def _number(said: str) -> float:
    """A passive's number as written: "12%" a share, "16" an amount."""
    said = said.strip()
    return float(said[:-1]) / 100 if said.endswith("%") else float(said)


def words_key(words: str) -> str:
    """A key of a passive's words (D303): what a reading by hand was read from, without
    keeping the game's words in the app."""
    return hashlib.sha256(_plain(words).encode("utf-8")).hexdigest()[:16]


def judge(data: dict, judged: dict) -> dict:
    """Each passive read by hand (D303) in place of the reader's, where the game's words still
    have the key of the ones it was read from -- at each rank, from the passive's own numbers. A
    weapon whose words changed, or that was never read by hand, keeps the reader's and is not
    `checked`: 更新 lists it."""
    by_hand = judged.get("weapons") or {}
    for name, arm in (data.get("weapons") or {}).items():
        entry = by_hand.get(name)
        arm["checked"] = bool(entry) and entry["key"] == words_key(arm.get("text") or "")
        if not arm["checked"]:
            continue
        params = arm.get("params") or []
        for rank in arm.get("buffs") or []:
            at = int(rank["rank"])

            def value(effect: dict, at: int = at, params: list = params) -> float:
                if "value" in effect:
                    return float(effect["value"])
                column = params[effect["param"]]
                # "提升{2}%": the number without its %, which the words put after it
                return _number(column[min(at, len(column)) - 1]) * float(effect.get("scale", 1))

            rank["effects"] = [
                {**{k: v for k, v in e.items() if k not in ("param", "scale")}, "value": value(e)}
                for e in entry["effects"]
            ]
            rank["not_counted"] = list(entry.get("notes") or [])
    # a set's pieces and a main echo (D305): their words are filled in, so each number is written
    by_set = judged.get("sets") or {}
    for name, entry in (data.get("sets") or {}).items():
        read = by_set.get(name) or {}
        entry["checked"], entry["notes"] = {}, {}
        for pieces, words in (entry.get("text") or {}).items():
            # the 2-piece's stat is the game's table's, not words read (D272)
            if pieces == "2" and entry.get("two") and "2" not in (entry.get("buffs") or {}):
                continue
            mine = read.get(pieces)
            ok = bool(mine) and mine["key"] == words_key(words)
            entry["checked"][pieces] = ok
            if ok:
                entry.setdefault("buffs", {})[pieces] = [dict(e) for e in mine["effects"]]
                entry["notes"][pieces] = list(mine.get("notes") or [])
    by_echo = judged.get("echoes") or {}
    for name, echo in (data.get("echoes") or {}).items():
        main = echo.get("main_buff")
        if not main:
            continue
        mine = by_echo.get(name)
        main["checked"] = bool(mine) and mine["key"] == words_key(main.get("text") or "")
        if main["checked"]:
            main["effects"] = [dict(e) for e in mine["effects"]]
            main["notes"] = list(mine.get("notes") or [])
    # states the game's data has no modes for (D314): 菲比's 赦罪 and 告解, as modes; a reading's
    # effect for one of them says which (`mode`). Never in place of the game's own modes.
    # 主C, 副C or 辅助 by hand (D315): how long they are on the field each round
    for name, kind in (judged.get("kinds") or {}).items():
        role = (data.get("roles") or {}).get(name)
        if role is not None and not role.get("kind"):
            role["kind"] = kind
    for name, modes in (judged.get("modes") or {}).items():
        role = (data.get("roles") or {}).get(name)
        if role is not None and not role.get("modes"):
            role["modes"] = [dict(m) for m in modes]
    # who has a shield of their own (D310): a shield row in their kit, or named by the readings --
    # a buff that needs one asks for this tag, as a status effect's asks for its own
    shields = set(judged.get("shields") or [])
    for name, role in (data.get("roles") or {}).items():
        rows = (row for skill in role.get("skills") or [] for row in skill.get("rows") or [])
        if name in shields or any(row.get("kind") == "shield" for row in rows):
            tags = role.setdefault("tags", [])
            if "护盾" not in tags:
                tags.append("护盾")
    # the sets the game recommends beyond its own tables (D310): 漂泊者·气动 shows three
    for name, sets in (judged.get("recommended") or {}).items():
        role = (data.get("roles") or {}).get(name)
        if role is None:
            continue
        have = role.setdefault("recommended", [])
        for set_name in sets:
            if not any(r["set"] == set_name and r.get("mode") is None for r in have):
                have.append({"set": set_name, "mode": None, "by": "hand"})
    # a resonator's own buffs and gifts (D306): by id, each reading with its words' key -- one id
    # can hold two paragraphs (爱弥斯's chain:6:121001), each read on its own
    by_role = judged.get("roles") or {}
    for name, role in (data.get("roles") or {}).items():
        read = by_role.get(name) or {}
        for buff in [*(role.get("buffs") or []), *(role.get("gives") or [])]:
            key = words_key(buff.get("text") or "")
            mine = next((o for o in read.get(buff["id"]) or [] if o["key"] == key), None)
            buff["checked"] = mine is not None
            if mine is not None:
                buff["effects"] = [dict(e) for e in mine["effects"]]
                buff["notes"] = list(mine.get("notes") or [])
                buff["rows"] = [dict(r) for r in mine.get("rows") or []]
            else:
                # the rows its words bring, as the reader reads them (D316)
                buff["rows"] = rows_of(buff.get("text") or "", buff.get("title") or "")
    _learned(data)
    return data


def _learned(data: dict) -> None:
    """What no hand has read yet -- new to the game, or its words changed -- read as the same
    words were by hand, whole or sentence by sentence (D317); the rest as the reader reads it.
    Still not `checked`: 更新 lists it, and `learned` says how it was read."""
    from .calc_learn import Memory

    memory = Memory()
    weapons = [a for a in (data.get("weapons") or {}).values() if a.get("buffs")]
    sets = list((data.get("sets") or {}).values())
    echoes = [e["main_buff"] for e in (data.get("echoes") or {}).values() if e.get("main_buff")]
    roles = list((data.get("roles") or {}).items())
    for arm in weapons:
        if arm.get("checked"):
            memory.learn(arm["buffs"][0]["text"], arm["buffs"][0].get("effects") or [])
    for entry in sets:
        for pieces, ok in (entry.get("checked") or {}).items():
            if ok:
                memory.learn(entry["text"][pieces], (entry.get("buffs") or {}).get(pieces) or [])
    for main in echoes:
        if main.get("checked"):
            memory.learn(main["text"], main.get("effects") or [])
    for name, role in roles:
        for buff in [*(role.get("buffs") or []), *(role.get("gives") or [])]:
            if buff.get("checked"):
                memory.learn(buff.get("text") or "", buff.get("effects") or [], who=name)

    # new lists and dicts, never the reader's changed in place: one may be another's too
    for arm in weapons:
        if arm.get("checked"):
            continue
        read = [memory.read(rank["text"], rank.get("effects") or []) for rank in arm["buffs"]]
        if all(how != "reader" for _, how in read):
            arm["buffs"] = [{**rank, "effects": effects}
                            for rank, (effects, _) in zip(arm["buffs"], read, strict=True)]
            arm["learned"] = read[0][1]
    for entry in sets:
        for pieces, ok in (entry.get("checked") or {}).items():
            if not ok and pieces in (entry.get("buffs") or {}):
                effects, how = memory.read(entry["text"][pieces], entry["buffs"][pieces])
                if how != "reader":
                    entry["buffs"] = {**entry["buffs"], pieces: effects}
                    entry["learned"] = {**(entry.get("learned") or {}), pieces: how}
    for main in echoes:
        if not main.get("checked"):
            effects, how = memory.read(main["text"], main.get("effects") or [])
            if how != "reader":
                main.update(effects=effects, learned=how)
    for name, role in roles:
        for buff in [*(role.get("buffs") or []), *(role.get("gives") or [])]:
            if not buff.get("checked"):
                effects, how = memory.read(buff.get("text") or "", buff.get("effects") or [],
                                           who=name)
                if how != "reader":
                    buff.update(effects=effects, learned=how)


def unchecked(data: dict) -> dict[str, list[str]]:
    """What 计算 counts by the reader, not by a reading by hand (D307): new to the game, or its
    words changed since -- for 更新 to say. By kind, as the page names them; empty kinds left
    out."""
    out = {
        "weapons": [n for n, a in (data.get("weapons") or {}).items() if not a.get("checked")],
        "sets": [f"{n} {p}" for n, s in (data.get("sets") or {}).items()
                 for p, ok in sorted((s.get("checked") or {}).items()) if not ok],
        "echoes": [n for n, e in (data.get("echoes") or {}).items()
                   if e.get("main_buff") and not e["main_buff"].get("checked")],
        "roles": [f"{n} · {b.get('title') or b['id']}"
                  for n, r in (data.get("roles") or {}).items()
                  for b in [*(r.get("buffs") or []), *(r.get("gives") or [])]
                  if not b.get("checked")],
    }
    # of those, the ones read as the same words were by hand (D317)
    out["learned"] = [
        *(n for n, a in (data.get("weapons") or {}).items()
          if not a.get("checked") and a.get("learned")),
        *(f"{n} {p}" for n, s in (data.get("sets") or {}).items()
          for p in sorted(s.get("learned") or {})),
        *(n for n, e in (data.get("echoes") or {}).items()
          if (e.get("main_buff") or {}).get("learned")),
        *(f"{n} · {b.get('title') or b['id']}" for n, r in (data.get("roles") or {}).items()
          for b in [*(r.get("buffs") or []), *(r.get("gives") or [])] if b.get("learned")),
    ]
    return {k: v for k, v in out.items() if v}


def load(directory: Path) -> dict | None:
    """calc.json from the catalogue folder, or None when it has not been fetched."""
    try:
        data = json.loads((Path(directory) / NAME).read_text(encoding="utf-8"))
        data = judge(_words_read_again(_effect_damage_dropped(_heal_rows_read(data))), JUDGED)
    except (OSError, ValueError):
        return None
    return _with_guides(data, directory)


def _with_guides(data: dict, directory: Path) -> dict:
    """The sets Kuro's official guides recommend join the game's (D313), marked `guide`."""
    from . import guides

    sets = data.get("sets") or {}
    by_id = {s["id"]: n for n, s in sets.items() if s.get("id") is not None}
    for name, entry in (guides.load(directory).get("roles") or {}).items():
        role = (data.get("roles") or {}).get(name)
        if role is None:
            continue
        have = role.setdefault("recommended", [])
        for set_name in guides.recommended_sets(entry, by_id):
            if sets and set_name not in sets:
                continue                # a set 计算's data does not know (yet)
            if not any(r["set"] == set_name and r.get("mode") is None for r in have):
                have.append({"set": set_name, "mode": None, "by": "guide"})
    return data


_CACHE: dict[str, tuple[tuple, dict | None]] = {}


def cached(directory: Path) -> dict | None:
    """`load`, read again only when the file changed (a fetch on 更新 replaces it)."""
    path = Path(directory) / NAME
    try:
        stamp = path.stat().st_mtime
    except OSError:
        return None
    # the guides beside it are read in too (D313): a fetch of them is a change
    guide = Path(directory) / "guides.json"
    stamp = (stamp, guide.stat().st_mtime if guide.exists() else None)
    key = str(path)
    if key not in _CACHE or _CACHE[key][0] != stamp:
        _CACHE[key] = (stamp, load(directory))
    return _CACHE[key][1]
