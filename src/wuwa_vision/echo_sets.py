# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""套装: every echo set, to look one up (D319).

What 计算's data already knows of each set, gathered for one page: its pieces' effects in the
game's words beside how 计算 reads them, who it is recommended for and by whom, the echoes it
comes in, and how many of the user's own echoes are in it. Headless: the page only shows it.
"""

from __future__ import annotations

from collections import Counter

from .calc import set_gives

#: What a set gives, as the page's 效果 chips name it, in the order they are shown: each stat an
#: effect raises falls under one of them (the element of a 属性伤害 is the 属性 chips' to say).
TAGS: dict[str, tuple[str, ...]] = {
    "属性伤害": ("dmg_1", "dmg_2", "dmg_3", "dmg_4", "dmg_5", "dmg_6", "dmg_all", "dmg_elem"),
    "攻击": ("atk_pct", "atk"),
    "生命": ("hp_pct", "hp"),
    "防御": ("def_pct", "def"),
    "暴击": ("crit",),
    "暴击伤害": ("crit_dmg",),
    "共鸣效率": ("er", "energy", "concerto"),
    "治疗": ("heal", "received", "shield"),
    "普攻": ("dmg_basic", "amplify_basic"),
    "重击": ("dmg_heavy", "amplify_heavy"),
    "共鸣技能": ("dmg_skill", "amplify_skill"),
    "共鸣解放": ("dmg_lib", "amplify_lib"),
    "变奏 · 延奏": ("dmg_intro", "dmg_outro", "amplify_intro", "amplify_outro"),
    "声骸技能": ("dmg_echo",),
    "伤害加深": ("amplify", "final", "taken", "mv"),
    "无视防御 · 抗性": ("def_ignore", "res_shred"),
    "偏谐": ("tune_eff",),
    "增益队友": (),
}
_TAG_OF = {stat: tag for tag, stats in TAGS.items() for stat in stats}
#: A buff scoped to one kind of hit also gives to that kind ("重击的暴击提升", D290).
_KIND_TAG = {"basic": "普攻", "heavy": "重击", "skill": "共鸣技能", "lib": "共鸣解放",
             "intro": "变奏 · 延奏", "outro": "变奏 · 延奏", "echo": "声骸技能"}
#: Who says a set is for a resonator, in the order the page lists them.
_BY_ORDER = ("game", "guide", "hand")


def pieces_of(entry: dict) -> list[int]:
    """The piece counts that turn an effect on: 2 and 5, 3 alone, or 1 (碎梦亡鬼之魇)."""
    return sorted(int(n) for n in (entry.get("text") or {}))


#: What a set's effect can need applied (D320), as 计算's conditions name it (D290): a status
#: effect on the enemy, or a 偏移; and the element each status effect belongs to.
_NEEDS_WORD = {"霜渐": "霜渐效应", "光噪": "光噪效应", "风蚀": "风蚀效应", "电磁": "电磁效应",
               "虚湮": "虚湮效应", "聚爆": "聚爆效应", "震谐响应": "震谐·偏移",
               "集谐响应": "集谐·偏移", "骇破响应": "骇破·偏移"}
NEED_ELEMENT = {"霜渐": 1, "聚爆": 2, "电磁": 3, "风蚀": 4, "光噪": 5, "虚湮": 6}


def needs_of(entry: dict) -> list[str]:
    """What the set's effect needs applied (D320), in the order its words say them: every
    【…效应】 or 【…·偏移】 its words name, and what 计算's reading asks for; with what may stand
    in for one ("添加【电磁效应】时，或自身获得同奏", 衔梦照世之心). A heal, a shield, or 同奏 alone
    is no status effect: a set that needs only those needs nothing here."""
    words = "".join((entry.get("text") or {}).values())
    found = {tag for tag, said in _NEEDS_WORD.items() if f"【{said}】" in words}
    for said in (entry.get("buffs") or {}).values():
        for effect in said:
            when = effect.get("when") or []
            if any(tag in _NEEDS_WORD for tag in when):
                found |= set(when) & ({*_NEEDS_WORD, "同奏"})
    said_at = {tag: words.find(_NEEDS_WORD.get(tag, tag)) for tag in found}
    return sorted(found, key=lambda t: (said_at[t] < 0, said_at[t], t))


def elements_of(entry: dict) -> list[int]:
    """The set's element as the 属性 chips find it (D320): its own; else the element of each status
    effect it needs, as 命理崩毁之弦's 虚湮效应 is 湮灭's; none for a set for anyone, or one that
    needs only a 偏移."""
    if entry.get("element"):
        return [entry["element"]]
    return list(dict.fromkeys(NEED_ELEMENT[t] for t in needs_of(entry) if t in NEED_ELEMENT))


def _effects(entry: dict) -> list[dict]:
    return [*(entry.get("two") or []),
            *(e for said in (entry.get("buffs") or {}).values() for e in said)]


def tags_of(entry: dict) -> list[str]:
    """What the set gives, as TAGS names it, in TAGS's order."""
    found: set[str] = set()
    for effect in _effects(entry):
        if effect.get("stat") in _TAG_OF:
            found.add(_TAG_OF[effect["stat"]])
        if effect.get("kind") in _KIND_TAG:
            found.add(_KIND_TAG[effect["kind"]])
        if effect.get("team") or effect.get("others"):
            found.add("增益队友")
    return [tag for tag in TAGS if tag in found]


def recommended_for(data: dict, name: str) -> list[dict]:
    """The resonators the set is recommended for (D272, D310, D313): each once, by the first who
    says it -- the game, then Kuro's guides, then the hand list -- with the mode the game gives."""
    out: dict[str, dict] = {}
    for who, role in (data.get("roles") or {}).items():
        for said in role.get("recommended") or []:
            if said.get("set") != name:
                continue
            by = said.get("by") or "game"
            mode = next((m["name"] for m in role.get("modes") or []
                         if m.get("id") == said.get("mode") and said.get("mode") is not None),
                        None)
            row = {"name": who, "by": by, "mode": mode.removeprefix("共鸣模态·") if mode else None,
                   "rarity": role.get("rarity"), "element": role.get("element")}
            have = out.get(who)
            if have is None or _BY_ORDER.index(by) < _BY_ORDER.index(have["by"]):
                out[who] = row
    return sorted(out.values(), key=lambda r: (_BY_ORDER.index(r["by"]), r["name"]))


def echoes_in(data: dict, name: str, pictures: dict) -> list[dict]:
    """The echoes the set comes in, the costliest first; an echo's other form (异相·) drawn as the
    echo it is a form of, as 计算's picker draws it (D269)."""
    icons = pictures.get("echoes") or {}
    rows = [{"name": n, "cost": e.get("cost"),
             "icon": icons.get(n) or icons.get(n.removeprefix("异相·"))}
            for n, e in (data.get("echoes") or {}).items() if name in (e.get("sets") or [])]
    return sorted(rows, key=lambda r: (-(r["cost"] or 0), r["name"]))


def worn(echoes_by_resonator: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Each set's pieces on each of the user's resonators, the most first."""
    out: dict[str, list[dict]] = {}
    for who, echoes in echoes_by_resonator.items():
        for set_name, count in Counter(e.get("set") for e in echoes if e.get("set")).items():
            out.setdefault(set_name, []).append({"name": who, "pieces": count})
    for rows in out.values():
        rows.sort(key=lambda r: (-r["pieces"], r["name"]))
    return out


def _how(entry: dict, pieces: str) -> str:
    """How 计算 counts these pieces (D272, D305, D317): the game's own table, read by hand,
    learned from the readings by hand, or the reader's alone."""
    if pieces == "2" and entry.get("two") and pieces not in (entry.get("buffs") or {}):
        return "table"
    if (entry.get("checked") or {}).get(pieces):
        return "hand"
    if (entry.get("learned") or {}).get(pieces):
        return "learned"
    return "reader"


def listing(data: dict, pictures: dict, mine: dict[str, list[dict]]) -> list[dict]:
    """Every set, in the game's order, as the page's grid shows it."""
    icons = pictures.get("sets") or {}
    counted: Counter[str] = Counter()
    for role in (data.get("roles") or {}).values():
        for said in {r.get("set") for r in role.get("recommended") or []}:
            counted[said] += 1
    rows = []
    for name, entry in (data.get("sets") or {}).items():
        rows.append({
            "name": name, "id": entry.get("id"), "element": entry.get("element"),
            "needs": needs_of(entry), "elements": elements_of(entry),
            "icon": icons.get(name), "pieces": pieces_of(entry), "gives": set_gives(entry),
            "tags": tags_of(entry), "recommended": counted[name],
            "mine": sum(r["pieces"] for r in mine.get(name) or []),
            "text": entry.get("text") or {},
            # for the search: a set is found by an echo it comes in
            "echoes": [e["name"] for e in echoes_in(data, name, {})],
        })
    return sorted(rows, key=lambda r: (r["id"] is None, r["id"] or 0, r["name"]))


def detail(data: dict, name: str, pictures: dict, mine: dict[str, list[dict]]) -> dict | None:
    """One set, everything the page's panel says of it; None for a set the data does not have."""
    entry = (data.get("sets") or {}).get(name)
    if entry is None:
        return None
    row = next(r for r in listing({**data, "sets": {name: entry}}, pictures, mine))
    counts = pieces_of(entry)
    pieces = []
    for n in counts:
        key = str(n)
        how = _how(entry, key)
        pieces.append({
            "pieces": n, "text": (entry.get("text") or {}).get(key, ""), "how": how,
            "effects": [dict(e) for e in (entry.get("two") if how == "table"
                                          else (entry.get("buffs") or {}).get(key)) or []],
            "notes": list((entry.get("notes") or {}).get(key) or []),
        })
    return {
        **row,
        "pieces": pieces,
        "counts": counts,
        "recommended": recommended_for(data, name),
        "echoes": echoes_in(data, name, pictures),
        "mine": [{**r, "on": [n for n in counts if r["pieces"] >= n]}
                 for r in mine.get(name) or []],
    }
