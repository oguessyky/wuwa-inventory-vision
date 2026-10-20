# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""What a dish or potion does, read out of the wiki's sentence (D114).

The wiki gives one sentence per item ("提高队伍中所有共鸣者12%攻击力和10%暴击率，
持续时间30分钟，…"). The pages want to filter by it and to show it at a glance,
so the sentence is taken apart into what changes and by how much, for how long,
for whom, and on what condition. Nothing here is a table of dishes: a new dish
that says the same kind of thing reads the same way, and one that says
something new simply has no parts and keeps its sentence.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

#: The kinds a page can filter by, in the order the chips are shown.
TAGS = ("攻击", "暴击", "伤害", "防御", "生命", "治疗", "回复", "能量", "耐力", "探索")

_ELEMENT = "冷凝|热熔|导电|气动|衍射|湮灭"
_N = r"(\d+(?:\.\d+)?)"

#: "N%X" / "N点X": (X as the wiki writes it, the label shown, the tag, lower-is-the-point).
#: Longest first, so 暴击伤害 is not read as 暴击 and 生命上限 not as 生命.
_AFTER_NUMBER: tuple[tuple[str, str, str, bool], ...] = (
    (r"治疗效果加成", "治疗效果", "治疗", False),
    (r"共鸣技能伤害加成", "共鸣技能伤害", "伤害", False),
    (r"共鸣解放伤害加成", "共鸣解放伤害", "伤害", False),
    (r"重击伤害加成", "重击伤害", "伤害", False),
    (r"普攻伤害加成", "普攻伤害", "伤害", False),
    # \3: the element; \1 and \2 are the number and its unit, in front
    (rf"的?({_ELEMENT})(?:属性)?伤害抗性", r"\3抗性", "防御", False),
    (rf"的?({_ELEMENT})(?:属性伤害|伤害加成)", r"\3伤害", "伤害", False),
    (r"翱翔耐力消耗", "翱翔耐力消耗", "耐力", True),
    (r"纵跑、游泳耐力消耗", "冲刺、游泳耐力消耗", "耐力", True),
    (r"钩[锁索]冷却时间", "钩索冷却", "探索", True),
    (r"生命上限", "生命上限", "生命", False),
    (r"共鸣效率", "共鸣效率", "能量", False),
    (r"暴击伤害", "暴击伤害", "暴击", False),
    (r"暴击率?", "暴击率", "暴击", False),
    (r"攻击力?", "攻击", "攻击", False),
    (r"防御力?", "防御", "防御", False),
    (r"耐力", "耐力", "耐力", False),
    (r"协奏能量", "协奏能量", "能量", False),
    (r"共鸣能量", "共鸣能量", "能量", False),
)
#: "X增加N%" / "X提升N%": the number comes after what it changes.
_BEFORE_NUMBER: tuple[tuple[str, str, str, bool], ...] = (
    (r"贝币增加", "击败敌人的贝币", "探索", False),
    (r"声骸吸收(?:概率)?提升", "声骸吸收", "探索", False),
    (r"素材掉落加成", "素材掉落", "探索", False),
    (r"声骸技能伤害提升", "声骸技能伤害", "伤害", False),
    (r"声骸技能冷却时间缩短", "声骸技能冷却", "伤害", True),
    (r"共鸣效率提升", "共鸣效率", "能量", False),
)
_DURATION = re.compile(rf"(?:持续(?:时间)?|生效的){_N}(分钟|秒)")
_COOLDOWN = re.compile(rf"每{_N}秒只能使用一次")
_CONDITION = re.compile(
    r"(对[^，。]*?敌人造成伤害时|释放变奏技能后|触发[^，。]+?时|首次受到致命伤害时)"
)
_HEAL_PERCENT = re.compile(rf"(?:生命上限{_N}%的生命值|回复{_N}%生命上限)")
_HEAL_FLAT = re.compile(rf"(?:{_N}点固定生命值|回复{_N}点生命值)")


@dataclass(frozen=True)
class Stat:
    tag: str
    label: str
    value: str
    """As shown: "+12%", "-20%", "+60", "每秒 +5"; empty when the sentence gives no number."""


@dataclass
class Effect:
    stats: list[Stat] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    duration: str | None = None
    """"30 分钟" / "15 秒"; None for something used up at once."""
    cooldown: str | None = None
    target: str | None = None
    """"全队" or "单人"."""
    condition: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def _number(n: str, unit: str, lower: bool) -> str:
    return f"{'-' if lower else '+'}{n}{'%' if unit == '%' else ''}"


def _healing(text: str) -> list[Stat]:
    """Sentences that give life back: on use, per second, on waking, on a fatal hit."""
    out: list[Stat] = []
    if "恢复意识" in text:
        out.append(Stat("回复", "复苏", ""))
    if "免疫该次伤害" in text:
        out.append(Stat("回复", "免疫一次致命伤害", ""))
    if not ("回复" in text and "生命" in text):
        return out
    each = "每秒 " if "每秒回复" in text else ""
    if "完全恢复生命" in text:
        out.append(Stat("回复", "生命", "回满"))
    percent = _HEAL_PERCENT.search(text)
    if percent:
        out.append(Stat("回复", "生命", f"{each}+{percent.group(1) or percent.group(2)}%"))
    flat = _HEAL_FLAT.search(text)
    if flat:
        out.append(Stat("回复", "生命", f"{each}+{flat.group(1) or flat.group(2)}"))
    return out


def parse(text: str | None) -> Effect | None:
    """The sentence as parts, or None when it says nothing this module knows."""
    text = (text or "").strip()
    if not text:
        return None
    stats = _healing(text)
    # What the healing clauses already said is taken out, so "生命上限30%的生命值"
    # is not read a second time as a 30% 生命上限 buff.
    rest = _HEAL_FLAT.sub("", _HEAL_PERCENT.sub("", text)) if stats else text
    found: list[tuple[int, Stat]] = []
    taken: list[tuple[int, int]] = []

    def free(span: tuple[int, int]) -> bool:
        return all(span[1] <= a or span[0] >= b for a, b in taken)

    for pattern, label, tag, lower in _AFTER_NUMBER:
        for m in re.finditer(rf"{_N}(%|点){pattern}", rest):
            if free(m.span()):
                taken.append(m.span())
                each = "每秒 " if "每秒回复" in rest and tag == "能量" else ""
                value = each + _number(m.group(1), m.group(2), lower)
                found.append((m.start(), Stat(tag, m.expand(label), value)))
    for pattern, label, tag, lower in _BEFORE_NUMBER:
        for m in re.finditer(rf"{pattern}{_N}(%)", rest):
            if free(m.span()):
                taken.append(m.span())
                found.append((m.start(), Stat(tag, label, _number(m.group(1), m.group(2), lower))))
    if "削减敌人一定比例的共振度" in rest:
        found.append((len(rest), Stat("伤害", "额外削减共振度", "")))
    stats += [stat for _, stat in sorted(found, key=lambda pair: pair[0])]
    if not stats:
        return None
    duration = _DURATION.search(text)
    cooldown = _COOLDOWN.search(text)
    condition = _CONDITION.search(text)
    return Effect(
        stats=stats,
        tags=[t for t in TAGS if any(s.tag == t for s in stats)],
        duration=f"{duration.group(1)} {duration.group(2)}" if duration else None,
        cooldown=f"{cooldown.group(1)} 秒" if cooldown else None,
        target="单人" if "指定共鸣者" in text else "全队" if "队伍" in text else None,
        condition=condition.group(1) if condition else None,
    )
