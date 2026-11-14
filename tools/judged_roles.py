# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Every resonator's own buffs and gifts, read by hand (D306): `tools/judged_buffs.py` writes them.

By resonator, by the buff's id as the data has it (`inherent:…`, `chain:n`, `outro:…`, a gift's
`…:1`). `OK` is a reading that agrees with the reader's, read and kept as it is; otherwise
(effects, notes), as for the weapons and sets (D303, D305): what the words raise, scoped to the
skill they name, its condition, for whom, and what is noted. A resonator's 协奏能量 and 共鸣能量
given back are `concerto` and `energy`, once a pass of their kit.
"""

from __future__ import annotations

OK = "ok"
HEAL = ["生存治疗"]
#: 菲比's two states as modes (D314): "长按 普攻 to get into 主c mode or 长按共鸣技能 to get 副C".
SHEZUI, GAOJIE = 9150601, 9150602
MODES = {
    "菲比": [{"id": SHEZUI, "name": "赦罪", "text": "长按普攻进入：主C，自己打伤害"},
             {"id": GAOJIE, "name": "告解", "text": "长按共鸣技能进入：副C，给队伍默祷"}],
}
#: Who is not a main DPS, nor a healer (D315): on the field shorter each round. The rest are 主C,
#: a healer 辅助; the page changes the seconds.
KINDS = {name: "副C" for name in (
    "散华", "莫特斐", "丹瑾", "渊武", "秧秧", "桃祈", "夏空", "坎特蕾拉", "洛可可", "釉瑚",
    "漂泊者·气动")}


def V(stat: str, value: float, **more: object) -> dict:
    return {"stat": stat, "value": value, **more}


def S(n: int) -> dict:
    return {"per_stack": True, "stacks": n}


NO_ROW = "额外的伤害不算：计算没有这一行"


def ROW(name: str, value: str, bonus: str | None = None, stat: str = "atk") -> dict:
    """An extra hit of its own number (D316): a third part of a reading, its rows."""
    return {"name": name, "kind": "damage", "stat": stat, "values": [value],
            **({"bonus": bonus} if bonus else {})}


def LIKE(name: str, like: str, share: float, bonus: str | None = None) -> dict:
    """An extra hit that is a share of another row's multiplier (D316)."""
    return {"name": name, "kind": "damage", "like": like, "share": share,
            **({"bonus": bonus} if bonus else {})}
FULL = "按满层算"

ROLES: dict[str, dict[str, object]] = {
    "秧秧": {
        "inherent:1000104": OK,
        "inherent:1000105": OK,
        "chain:1": OK,
        "chain:2": ([V("energy", 10)], []),
        "chain:3": OK,
        "chain:4": OK,
        "chain:5": OK,
        "chain:6": OK,
        "chain:6:1": OK,
    },
    "炽霞": {
        "inherent:1000204": OK,
        "inherent:1000205": OK,
        "chain:1": ([V("crit", 1.0, skill="轰轰")], []),
        "chain:2": ([], ["击败目标回复的共鸣能量不算"]),
        "chain:3": ([], ["对生命低于一半的目标才有：不算"]),
        "chain:4": OK,
        "chain:5": OK,
        "chain:6": OK,
        "chain:6:1": OK,
    },
    "维里奈": {
        "inherent:1000304": OK,
        "inherent:1000305": OK,
        "chain:1": OK,
        "chain:2": ([V("concerto", 10)], []),
        "chain:3": OK,
        "chain:4": OK,
        "chain:5": ([], ["治疗生命低于一半的角色时才有：不算"]),
        "chain:6": OK,
        "inherent:1000305:1": OK,
        "outro:1000309": OK,
        "chain:4:1": OK,
        "chain:6:1": ([], ["给队伍的是治疗，不是伤害"]),
    },
    "漂泊者·衍射": {"inherent:1000604": OK, "inherent:1000605": OK},
    "散华": {
        "inherent:1000504": OK,
        "inherent:1000505": OK,
        "chain:1": OK,
        "chain:2": OK,
        "chain:3": ([V("final", 0.35)], ["按目标生命低于 70% 算"]),
        "chain:4": ([V("energy", 10), V("dmg_heavy", 1.2, skill="爆裂")], []),
        "chain:5": OK,
        "chain:6": OK,
        "outro:1000509": OK,
        "chain:6:1": OK,
    },
    "桃祈": {
        "inherent:1000904": OK,
        "inherent:1000905": OK,
        "chain:1": ([V("shield", 0.4)], ["只有攻防转换的护盾"]),
        "chain:2": ([V("crit", 0.2, skill="不动如山"), V("crit_dmg", 0.2, skill="不动如山")], []),
        "chain:3": OK,
        "chain:4": OK,
        "chain:5": ([V("dmg_all", 0.5, skill="攻防转换"), V("energy", 20)], []),
        "chain:6": ([V("dmg_basic", 0.4), V("dmg_heavy", 0.4)], ["按护盾在时算"]),
        "outro:1000909": OK,
    },
    "白芷": {
        "inherent:1000404": ([V("atk_pct", 0.15, team=True)], ["给拾取天籁的角色"]),
        "inherent:1000405": OK,
        "chain:1": ([V("energy", 10)], ["按 4 点【念意】算"]),
        "chain:2": OK,
        "chain:3": OK,
        "chain:4": OK,
        "chain:5": OK,
        "chain:6": OK,
        "outro:1000409": OK,
        "chain:6:1": OK,
    },
    "安可": {
        "inherent:1000704": OK,
        "inherent:1000705": OK,
        "chain:1": OK,
        "chain:2": ([V("energy", 10)], []),
        "chain:3": (
            [
                V("mv", 0.4, kind="heavy", skill="白咩·失控之炎"),
                V("mv", 0.4, kind="heavy", skill="黑咩·暴走之炎"),
            ],
            [],
        ),
        "chain:4": OK,
        "chain:5": OK,
        "chain:6": ([V("atk_pct", 0.05, **S(5))], [FULL]),
        "chain:4:1": OK,
    },
    "丹瑾": {
        "inherent:1000804": OK,
        "inherent:1000805": OK,
        "chain:1": OK,
        "chain:2": OK,
        "chain:3": OK,
        "chain:4": OK,
        "chain:5": (
            [V("dmg_6", 0.15), V("dmg_6", 0.15)],
            ["额外 15% 按生命低于 60% 算：她的技能会扣血"],
        ),
        "chain:6": OK,
        "outro:1000809": OK,
        "chain:6:1": OK,
    },
    "秋水": {
        "inherent:1001004": ([], ["每 30 秒一次的必定暴击不算"]),
        "inherent:1001005": OK,
        "chain:1": OK,
        "chain:2": ([V("atk_pct", 0.15)], ["分身继承的生命不是秋水自己的"]),
        "chain:3": ([], [], [LIKE("雾气子弹", "空中攻击", 0.5, "basic")]),
        "chain:4": OK,
        "chain:5": OK,
        "chain:6": ([V("crit", 0.08), V("dmg_heavy", 0.5)], []),
        "outro:1001009": OK,
    },
    "忌炎": {
        "inherent:1001104": OK,
        "inherent:1001105": OK,
        "chain:1": OK,
        "chain:2": OK,
        "chain:3": OK,
        "chain:4": OK,
        "chain:5": OK,
        "chain:6": ([V("mv", 1.2, kind="lib", skill="苍躣八荒·后动", **S(2))], []),
        "chain:4:1": OK,
    },
    "莫特斐": {
        "inherent:1001204": OK,
        "inherent:1001205": ([V("dmg_lib", 0.015, skill="加强音", **S(50))], [FULL]),
        "chain:1": ([], [], [LIKE("协同·加强音", "加强音伤害", 2, "lib")]),
        "chain:2": ([V("energy", 10)], []),
        "chain:3": OK,
        "chain:4": OK,
        "chain:5": ([], [], [LIKE("协同·加强音", "加强音伤害", 2, "lib")]),
        "chain:6": OK,
        "outro:1001209": OK,
        "chain:6:1": OK,
    },
    "椿": {
        "inherent:1001304": OK,
        "inherent:1001305": OK,
        "chain:1": OK,
        "chain:2": OK,
        "chain:3": OK,
        "chain:4": OK,
        "chain:5": OK,
        "chain:6": OK,
        "chain:4:1": OK,
    },
    "卡卡罗": {
        "inherent:1001404": OK,
        "inherent:1001405": OK,
        "chain:1": ([V("energy", 10)], []),
        "chain:2": OK,
        "chain:3": OK,
        "chain:4": OK,
        "chain:5": ([V("dmg_intro", 0.5)], []),
        "chain:6": ([], [], [ROW("猎杀影", "100.00%*2", "lib")]),
        "chain:4:1": OK,
    },
    "吟霖": {
        "inherent:1001504": OK,
        "inherent:1001505": OK,
        "chain:1": (
            [V("dmg_skill", 0.7, skill="磁殛咆哮"), V("dmg_skill", 0.7, skill="召雷磁爆")],
            [],
        ),
        "chain:2": ([V("energy", 5)], []),
        "chain:3": OK,
        "chain:4": OK,
        "chain:5": ([V("dmg_lib", 1.0, skill="破天雷灭击")], ["按目标带着缚罪标记算"]),
        "chain:6": ([], [], [ROW("疾霆昭彰", "419.59%*4", "skill")]),
        "outro:1001509": OK,
        "chain:4:1": OK,
    },
    "凌阳": {
        "inherent:1001804": OK,
        "inherent:1001805": ([], [], [LIKE("额外的翻山越涧", "飞身式·翻山越涧伤害", 1.5, "skill")]),
        "chain:1": OK,
        "chain:2": ([V("energy", 10)], []),
        "chain:3": OK,
        "chain:4": OK,
        "chain:5": ([], [], [ROW("五链·额外伤害", "200.00%")]),
        "chain:6": ([], ["只给下一次普攻：不算"]),
        "chain:4:1": OK,
    },
    "渊武": {
        "inherent:1001604": OK,
        "inherent:1001605": OK,
        "chain:1": OK,
        "chain:2": ([V("energy", 15)], []),
        "chain:3": ([], ["按防御加的伤害不算"]),
        "chain:4": ([], ["给队伍的是护盾"]),
        "chain:5": OK,
        "chain:6": OK,
        "chain:6:1": OK,
    },
    "漂泊者·湮灭": {
        "inherent:1001704": OK,
        "inherent:1001705": ([V("energy", 4)], ["按一遍普攻约 4 次命中算"]),
        "chain:1": OK,
        "chain:2": OK,
        "chain:3": OK,
        "chain:4": ([V("res_shred", 0.1, element=6, team=True)], []),
        "chain:5": ([], [], [LIKE("暗涌·额外伤害", "暗流·普攻第五段伤害", 0.5, "basic")]),
        "chain:6": OK,
    },
    "鉴心": {
        "inherent:1001904": OK,
        "inherent:1001905": ([V("shield", 0.2)], []),
        "chain:1": OK,
        "chain:2": OK,
        "chain:3": OK,
        "chain:4": OK,
        "chain:5": OK,
        "chain:6": ([], [], [ROW("特殊行气反击", "556.67%", "heavy")]),
        "outro:1001909": OK,
    },
    "今汐": {
        "inherent:1002004": OK,
        "inherent:1002005": OK,
        "chain:1": ([V("final", 0.2, kind="skill", skill="惊龙破空", **S(4))], [FULL]),
        "chain:2": OK,
        "chain:3": OK,
        "chain:4": OK,
        "chain:5": OK,
        "chain:6": (
            [
                V("mv", 0.45, kind="skill", skill="惊龙破空"),
                V("mv", 0.45, kind="skill", skill="惊龙破空"),
            ],
            ["韶光带来的倍率额外提升，也按惊龙破空的倍率算"],
        ),
        "chain:4:1": OK,
    },
    "相里要": {
        "inherent:1002304": OK,
        "inherent:1002305": OK,
        "chain:1": ([], [], [LIKE("衍构模体", "万方法则伤害", 0.48, "lib")]),
        "chain:2": OK,
        "chain:3": (
            [V("dmg_skill", 0.63, skill=s) for s in ("应刃", "基本推衍", "一相万殊", "万方法则")],
            [],
        ),
        "chain:4": OK,
        "chain:5": OK,
        "chain:6": OK,
        "chain:4:1": OK,
    },
    "长离": {
        "inherent:1002104": ([V("dmg_2", 0.05, **S(4))], ["按 4 层【离火】算"]),
        "inherent:1002105": OK,
        "chain:1": OK,
        "chain:2": OK,
        "chain:3": OK,
        "chain:4": OK,
        "chain:5": OK,
        "chain:6": (
            [V("def_ignore", 0.4, skill=s) for s in ("赫羽三相", "焚身以火", "离火照丹心")],
            [],
        ),
        "outro:1002109": OK,
        "chain:4:1": OK,
    },
    "折枝": {
        "inherent:1002204": OK,
        "inherent:1002205": ([], ["给下一位的 15 点共鸣能量不算在她自己身上"]),
        "chain:1": ([V("energy", 15), V("crit", 0.1)], []),
        "chain:2": OK,
        "chain:3": OK,
        "chain:4": OK,
        "chain:5": ([], [], [LIKE("协同墨鹤", "墨鹤伤害", 1.4, "basic")]),
        "chain:6": ([], [], [LIKE("白鹤", "神来之笔伤害", 1.2, "basic")]),
        "outro:1002209": OK,
    },
    "灯灯": {
        "inherent:1002604": OK,
        "inherent:1002605": OK,
        "chain:1": OK,
        "chain:2": ([V("def_ignore", 0.2, skill=s) for s in ("强化·前扑", "强化·后撤")], []),
        "chain:3": OK,
        "chain:4": OK,
        "chain:5": OK,
        "chain:6": OK,
        "outro:1002609": OK,
        "chain:6:1": OK,
    },
    "釉瑚": {
        "inherent:1002404": OK,
        "inherent:1002405": OK,
        "chain:1": OK,
        "chain:2": OK,
        "chain:3": OK,
        "chain:4": OK,
        "chain:5": OK,
        "chain:6": ([V("crit_dmg", 0.15, **S(4))], [FULL]),
        "outro:1002409": ([V("amplify", 1.0, skill="协同攻击")], []),
    },
    "守岸人": {
        "inherent:1002504": OK,
        "inherent:1002505": ([V("er", 0.1)], ["漂泊者的那份是给漂泊者的"]),
        "chain:1": OK,
        "chain:2": ([V("atk_pct", 0.4, team=True)], []),
        "chain:3": ([V("concerto", 20)], []),
        "chain:4": OK,
        "chain:5": OK,
        "chain:6": (
            [V("mv", 0.42, kind="intro", skill="洞悉"), V("crit_dmg", 5.0, skill="洞悉")],
            [],
        ),
        "skill:1002503:1": OK,
        "skill:1002503:2": OK,
        "outro:1002509": OK,
        "chain:2:1": ([V("atk_pct", 0.4, team=True)], []),
    },
    "洛可可": {
        "inherent:1002704": OK,
        "inherent:1002705": ([], ["给下一位的【珍奇箱】不算"]),
        "chain:1": ([V("concerto", 10)], []),
        "chain:2": OK,
        "chain:3": OK,
        "chain:4": OK,
        "chain:5": (
            [V("mv", 0.2, kind="lib", skill="即兴喜剧，开场"), V("mv", 0.8, kind="heavy")],
            [],
        ),
        "chain:6": ([V("def_ignore", 0.6, skill="幻想照进现实")], []),
        "outro:1002709": OK,
        "chain:2:1": OK,
    },
    "珂莱塔": {
        "inherent:1002804": OK,
        "inherent:1002805": OK,
        "chain:1": OK,
        "chain:2": OK,
        "chain:3": (
            [
                V("mv", 0.93, kind="skill", skill="暴力美学"),
                V("mv", 0.93, kind="skill", skill="示我璀璨"),
            ],
            [],
            [ROW("碎璃镜花", "1032.18%", "outro")],
        ),
        "chain:4": OK,
        "chain:5": OK,
        "chain:6": OK,
        "chain:4:1": OK,
    },
    "布兰特": {
        "inherent:1002904": ([V("heal", 0.2, skill="涛声喝彩")], []),
        "inherent:1002905": OK,
        "chain:1": ([V("final", 0.2, **S(3))], [FULL]),
        "chain:2": (
            [V("crit", 0.3, skill="空中攻击"), V("crit", 0.3, skill="火焰归亡曲")],
            [],
            [ROW("航向确定·爆炸", "440.00%*2", "basic")],
        ),
        "chain:3": OK,
        "chain:4": OK,
        "chain:5": ([V("dmg_basic", 0.15)], []),
        "chain:6": ([V("mv", 0.3, skill="空中攻击")], [], [LIKE("再燃", "火焰归亡曲伤害", 0.3, "basic")]),  # noqa: E501
        "outro:1002909": OK,
    },
    "菲比": {
        "inherent:1003004": OK,
        "inherent:1003005": OK,
        "chain:1": (
            [V("mv", 0.9, kind="lib", skill="启明之誓愿", mode=GAOJIE)],
            ["赦罪状态：倍率提升从255%变为480%，原有的提升计算里没有，所以没算"],
        ),
        "chain:2": (
            [
                V("amplify", 1.2, kind="outro", when=["光噪"], mode=SHEZUI),
                V("amplify", 1.2, effect="光噪", team=True, mode=GAOJIE),
            ],
            [],
        ),
        "chain:3": (
            [
                V("mv", 0.91, kind="heavy", skill="星辉", mode=SHEZUI),
                V("mv", 2.49, kind="heavy", skill="星辉", mode=GAOJIE),
            ],
            [],
        ),
        "chain:4": ([V("res_shred", 0.1, element=5, team=True)], []),
        "chain:5": OK,
        "chain:6": OK,
        "outro:1003009": (
            [
                V("res_shred", 0.1, element=5, team=True, mode=GAOJIE),
                V("amplify", 1.0, effect="光噪", team=True, mode=GAOJIE),
            ],
            [],
        ),
    },
    "漂泊者·气动": {
        "inherent:1003204": OK,
        "inherent:1003205": ([V("heal", 0.2, skill="万象归墟")], []),
        "chain:1": OK,
        "chain:2": OK,
        "chain:3": OK,
        "chain:4": OK,
        "chain:5": OK,
        "chain:6": OK,
    },
    "坎特蕾拉": {
        "inherent:1003104": OK,
        "inherent:1003105": OK,
        "chain:1": ([V("mv", 0.5, skill=s) for s in ("翩跹", "斑驳幻梦", "感知汲取")], []),
        "chain:2": OK,
        "chain:3": OK,
        "chain:4": OK,
        "chain:5": OK,
        "chain:6": OK,
        "outro:1003109": OK,
    },
    "夏空": {
        "inherent:1003404": OK,
        "inherent:1003405": OK,
        "chain:1": OK,
        "chain:2": ([V("dmg_4", 0.4, team=True)], []),
        "chain:3": OK,
        "chain:4": (
            [
                V("def_ignore", 0.45, kind="heavy", skill="四拍重奏"),
                V("def_ignore", 0.45, kind="lib"),
            ],
            [],
        ),
        "chain:5": OK,
        "chain:6": ([], [], [ROW("音律独奏", "220.00%", "lib")]),
        "outro:1003409": OK,
        "chain:2:1": ([V("dmg_4", 0.4, team=True)], []),
    },
    "赞妮": {
        "inherent:1003304": OK,
        "inherent:1003305": OK,
        "chain:1": OK,
        "chain:2": (
            [V("crit", 0.2), V("mv", 0.8, skill="集中压制"), V("mv", 0.8, skill="破袭反击")],
            [],
        ),
        "chain:3": (
            [V("mv", 0.08, kind="lib", skill="终绝将至之刻", **S(150))],
            ["按消耗满 150 点【焰光】算"],
        ),
        "chain:4": OK,
        "chain:5": OK,
        "chain:6": (
            [V("mv", 0.4, skill=s) for s in ("重斩·破晓", "重斩·将明", "重斩·终夜", "重斩·闪裂")],
            ["每点【焰光】额外的倍率没算"],
        ),
        "outro:1003309": (
            [V("amplify", 0.2, element=5, others=True)],
            ["延奏自己的那一下伤害不算：计算没有这一行"],
        ),
        "chain:4:1": OK,
    },
    "露帕": {
        "inherent:1003604": OK,
        "inherent:1003605": (
            [V("res_shred", 0.03, element=2, team=True)],
            ["队伍里每多一名热熔角色再加的部分不算"],
        ),
        "chain:1": ([V("concerto", 10), V("crit", 0.2)], []),
        "chain:2": OK,
        "chain:3": (
            [
                V("mv", 1.0, kind="intro", skill="你无法逃离！"),
                V("res_shred", 0.12, element=2, team=True),
            ],
            ["荣光的无视热熔抗性合计 15%"],
        ),
        "chain:4": OK,
        "chain:5": OK,
        "chain:6": (
            [
                V("def_ignore", 0.3, skill=s)
                for s in ("狼舞的决意·极", "荣光欢酣于火", "你无法逃离！")
            ],
            [],
        ),
        "skill:1003603:1": (
            [V("atk_pct", 0.18, team=True), V("dmg_2", 0.1, team=True)],
            ["攻击按队伍三次变奏叠满 18% 算", "热熔加成按打怒涛、海啸级目标算"],
        ),
        "outro:1003609": OK,
        "chain:2:1": OK,
    },
    "弗洛洛": {
        "inherent:1003704": OK,
        "inherent:1003705": ([V("crit_dmg", 0.025, **S(10))], ["余响溢出后额外的暴击伤害不算"]),
        "chain:1": OK,
        "chain:2": (
            [V("mv", 0.75, skill="谱曲终末"), V("mv", 0.75, skill="谱曲终末")],
            ["余响带来的倍率额外提升，也按谱曲终末的倍率算"],
        ),
        "chain:3": OK,
        "chain:4": OK,
        "chain:5": OK,
        "chain:6": (
            [V("mv", 0.24, skill="强化攻击·赫卡忒"), V("dmg_6", 0.6)],
            ["算的是她在场时的湮灭加成；不在场时的 40% 没算"],
        ),
        "outro:1003709": OK,
        "chain:4:1": OK,
        "chain:6:1": ([], ["是弗洛洛自己的，不给队伍"]),
        "chain:6:2": ([], ["是弗洛洛自己的，不给队伍"]),
    },
    "卡提希娅": {
        "inherent:1003504": ([V("received", 0.2, others=True)], []),
        "inherent:1003505": (
            [V("final", 0.3, when=["风蚀"]), V("final", 0.1, when=["风蚀"], **S(3))],
            [FULL],
        ),
        "chain:1": ([V("crit_dmg", 0.25, skill="芙露德莉斯", **S(4))], [FULL]),
        "chain:2": (
            [
                V("mv", 0.5, kind="basic"),
                V("mv", 0.5, kind="heavy"),
                V("mv", 0.5, kind="intro"),
                V("mv", 2.0, skill="空中攻击"),
            ],
            ["芙露德莉斯形态的招式也一起算了"],
        ),
        "chain:3": ([V("mv", 1.0, kind="lib", skill="看潮怒风哮之刃")], []),
        "chain:4": OK,
        "chain:5": OK,
        "chain:6": ([V("final", 0.4, skill="芙露德莉斯")], []),
        "inherent:1003504:1": ([V("received", 0.2)], []),
        "outro:1003509": (
            [V("amplify", 0.175, element=4, when=["光噪", "电磁", "聚爆", "虚湮", "霜渐", "风蚀"])],
            [],
        ),
        "chain:4:1": OK,
    },
    "奥古斯塔": {
        "inherent:1003904": OK,
        "inherent:1003905": OK,
        "chain:1": ([V("crit_dmg", 0.15, **S(2))], []),
        "chain:2": (
            [
                V("crit", 0.2, **S(2)),
                V("crit_dmg", 1.0, needs={"stat": "crit", "value": 1.5, "from": 1.0}),
            ],
            [],
        ),
        "chain:3": (
            [
                V("mv", 0.25, skill=s)
                for s in (
                    "烁雷·后撤",
                    "烁雷·旋切",
                    "烁雷·升拳",
                    "不败恒阳·落袭",
                    "赫日威临·烈阳",
                    "赫日威临·不朽者之肃",
                )
            ],
            [],
        ),
        "chain:4": OK,
        "chain:5": OK,
        "chain:6": (
            [V("crit_dmg", 0.5, needs={"stat": "crit", "value": 1.75, "from": 1.5})],
            ["【以众愿为冕】上限到 4 层的部分不算"],
            [ROW("怒霆", "100.00%*2", "heavy")],
        ),
        "chain:4:1": OK,
    },
    "尤诺": {
        "inherent:1003804": OK,
        "inherent:1003805": OK,
        "chain:1": ([V("atk_pct", 0.4)], ["满月领域里每秒回的共鸣能量不算"]),
        "chain:2": ([V("amplify", 0.4, team=True)], ["按祝颂叠满 10 层算"]),
        "chain:3": (
            [V("amplify", 0.65, skill=s) for s in ("月弓·普攻", "越限的弦引", "月弓·闪避反击")],
            [],
        ),
        "chain:4": OK,
        "chain:5": OK,
        "chain:6": OK,
        "outro:1003809": OK,
    },
    "卜灵": {
        "inherent:1004304": ([], ["治疗生命低于一半的角色时才有：不算"]),
        "inherent:1004305": OK,
        "chain:1": ([V("crit", 0.2, skill="飞雷诀·归一")], []),
        "chain:2": ([V("energy", 25)], []),
        "chain:3": OK,
        "chain:4": OK,
        "chain:5": OK,
        "chain:6": ([], ["队伍共鸣技能加成提升到 50%：原来的数值不知道，没算"]),
        "outro:1004309": OK,
    },
    "嘉贝莉娜": {
        "inherent:1004004": ([V("amplify", 0.05, **S(4))], [FULL]),
        "inherent:1004005": OK,
        "chain:1": (
            [
                V("crit_dmg", 0.8, skill=s)
                for s in ("炽天猎杀", "炼羽裁决", "火狱暴雨", "掠袭", "罪业当涤")
            ],
            ["按满 40 点【余火】算"],
        ),
        "chain:2": ([], ["内燃烧原来的攻击加成不知道，没算"]),
        "chain:3": OK,
        "chain:4": OK,
        "chain:5": (
            [V("mv", 1.5, kind="skill", skill=s) for s in ("迫近", "恶翼扬升", "掠袭")],
            [],
        ),
        "chain:6": (
            [V("mv", 0.6, skill=s) for s in ("炽天猎杀", "炼羽裁决", "火狱暴雨", "罪业当涤")]
            + [
                V("amplify", 0.35, skill=s)
                for s in ("炽天猎杀", "炼羽裁决", "火狱暴雨", "掠袭", "罪业当涤")
            ],
            ["热熔加深按满 40 点【余火】算"],
        ),
        "chain:4:1": OK,
    },
    "千咲": {
        "inherent:1004204": OK,
        "inherent:1004205": ([V("dmg_6", 0.2), V("heal", 0.2)], []),
        "chain:1": ([V("atk_pct", 0.3)], ["61803 点固定伤害不算"]),
        "chain:2": ([V("res_shred", 0.1, element=6), V("dmg_all", 0.5, team=True)], []),
        "chain:3": (
            [V("mv", 1.2, skill=s) for s in ("锯环·疾攻", "电锯模式·闪避反击", "锯环·终结")],
            ["【锯环残响】带来的额外倍率不算"],
        ),
        "chain:4": OK,
        "chain:5": OK,
        "chain:6": (
            [V("final", 0.4), V("amplify", 0.3, effect="虚湮", team=True)],
            ["异常效应伤害加深按虚湮算"],
        ),
    },
    "仇远": {
        "inherent:1004104": (
            [V("final", 0.5, skill=s) for s in ("答剑·弦歌不辍", "答剑·割股之心", "答剑·忠烈死节")]
            + [V("concerto", 30)],
            [],
        ),
        "inherent:1004105": OK,
        "chain:1": OK,
        "chain:2": OK,
        "chain:3": (
            [V("mv", 5.0, kind="lib", skill="万钧一断")]
            + [V("mv", 6.0, skill=s) for s in ("答剑·弦歌不辍", "答剑·割股之心", "答剑·忠烈死节")],
            ["荷蓑出林和新筠坠箨的伤害不算：计算没有这一行"],
        ),
        "chain:4": OK,
        "chain:5": OK,
        "chain:6": ([V("crit_dmg", 1.0)], [], [ROW("退出淋漓醉墨", "600.00%", "echo")]),
        "skill:1004107:1": OK,
        "outro:1004109": OK,
        "chain:2:1": OK,
    },
    "琳奈": {
        "inherent:1004504": OK,
        "inherent:1004505": OK,
        "chain:1": ([V("mv", 1.2, kind="basic", skill="幻光折跃")], []),
        "chain:2": ([V("amplify", 0.25)], ["给下一位的 25% 在她的延奏里"]),
        "chain:3": (
            [
                V("mv", 0.9, kind="basic", skill="视觉冲击"),
                V("mv", 0.9, kind="basic", skill="虹彩飞溅"),
                V("dmg_5", 0.55, skill="加色混合", **S(25)),
            ],
            ["预调色按满 25 层算"],
        ),
        "chain:4": OK,
        "chain:5": ([V("mv", 0.7, kind="lib", skill="爆炸喷涂")], []),
        "chain:6": (
            [V("final", 0.3, skill="虹彩飞溅", **S(3)), V("final", 0.3, skill="视觉冲击", **S(3))],
            [FULL],
        ),
        "skill:1004503:1": OK,
        "outro:1004509": OK,
        "chain:2:1": OK,
    },
    "莫宁": {
        "inherent:1004404": ([V("er", 0.1), V("concerto", 40)], []),
        "inherent:1004405": OK,
        "chain:1": OK,
        "chain:2": (
            [
                V("crit_dmg", 0.32, team=True, needs={"stat": "er", "value": 2.6, "from": 1.0}),
                V("tune_eff", 0.2, team=True),
            ],
            ["暴击伤害对带着干涉标记的目标"],
        ),
        "chain:3": ([V("concerto", 25)], []),
        "chain:4": ([V("heal", 0.3, skill="强谐振场")], []),
        "chain:5": (
            [V("mv", 0.4, kind="lib", skill="临界协议"), V("mv", 1.6, skill="粒子射流")],
            [],
        ),
        "chain:6": ([V("final", 4.0, kind="lib", skill="临界协议")], []),
        "skill:1004403:1": ([V("def_pct", 0.2, team=True)], []),
        "skill:1004407:1": ([V("tune_eff", 0.5, team=True)], []),
        "outro:1004409": OK,
        "chain:2:1": ([V("tune_eff", 0.2, team=True)], []),
    },
    "陆·赫斯": {
        "inherent:1004704": OK,
        "inherent:1004705": (
            [V("amplify", 0.3, when=["集谐响应"]), V("atk_pct", 0.25, when=["集谐响应"])],
            ["伤害加深按满 30% 算"],
        ),
        "chain:1": OK,
        "chain:2": (
            [V("mv", 0.6, kind="lib", skill="于永冻中释义"), V("amplify", 0.3, when=["集谐响应"])],
            ["无因的医谕的加深上限提到 60%"],
        ),
        "chain:3": ([V("mv", 1.36, skill=s) for s in ("斩杀日冕", "判决大地裂响", "日髓阵列")], []),
        "chain:4": OK,
        "chain:5": (
            [
                V("dmg_intro", 0.8),
                V("dmg_outro", 0.8),
                V("mv", 0.5, kind="skill", skill="流金回潮"),
            ],
            [],
        ),
        "chain:6": (
            [V("final", 0.3, skill=s) for s in ("斩杀日冕", "日髓阵列", "判决大地裂响")]
            + [V("dmg_lib", 1.2, skill="于永冻中释义")],
            ["【终局之释义】按满层算"],
        ),
        "chain:4:1": OK,
    },
    "爱弥斯": {
        "inherent:1004604": (
            [
                V("amplify", 2.0, kind="heavy", skill="重击·爱弥斯"),
                V("amplify", 2.0, kind="heavy", skill="重击·机兵"),
            ],
            [],
        ),
        "inherent:1004605:121001": OK,
        "inherent:1004605:121002": OK,
        "chain:1": (
            [
                V("crit_dmg", 3.0, kind="heavy", skill="重击·爱弥斯"),
                V("crit_dmg", 3.0, kind="heavy", skill="重击·机兵"),
            ],
            [],
        ),
        "chain:1:121001": OK,
        "chain:2": OK,
        "chain:2:121001": OK,
        "chain:2:121002": ([], ["聚爆效应的倍率提升：计算的异常效应伤害只算光噪"]),
        "chain:3": OK,
        "chain:3:121001": OK,
        "chain:3:121002": OK,
        "chain:4": OK,
        "chain:5": OK,
        "chain:6": ([V("final", 0.4, kind="lib")], []),
        "chain:6:121001": ([], ["震谐伤害可暴击、轨迹上限：计算没有这一行"]),
        "chain:6:121002": OK,
        "outro:1004609": OK,
        "outro:1004609:2": OK,
        "chain:4:1": OK,
    },
    "西格莉卡": {
        "inherent:1005104": OK,
        "inherent:1005105": (
            [
                V("dmg_4", 0.03, team=True, **S(6)),
                V("dmg_echo", 0.03, team=True, **S(6)),
                V("dmg_4", 0.3),
                V("dmg_echo", 0.3),
                V("dmg_echo", 0.5, needs={"stat": "er", "value": 1.5, "from": 1.25}),
            ],
            ["语义的祝福按满 6 层算"],
        ),
        "chain:1": (
            [V("mv", 0.7, skill=s) for s in ("明悟", "解读", "大嘭嘭！", "日灵帮帮忙")],
            [],
        ),
        "chain:2": ([V("mv", 1.2, skill="我即语义")], []),
        "chain:3": OK,
        "chain:4": OK,
        "chain:5": OK,
        "chain:6": (
            [V("final", 0.3)]
            + [V("amplify", 0.6, skill=s) for s in ("符语爆破", "符语链刃", "符语日灵", "我即语义")]
            + [
                V("def_ignore", 0.3, skill=s)
                for s in ("符语爆破", "符语链刃", "符语日灵", "我即语义")
            ],
            ["「天赋？」按满层算"],
        ),
        "inherent:1005105:1": (
            [V("dmg_4", 0.03, team=True, **S(6)), V("dmg_echo", 0.03, team=True, **S(6))],
            [FULL],
        ),
        "chain:4:1": OK,
    },
    "达妮娅": {
        "inherent:1005304": OK,
        "inherent:1005305": (
            [V("dmg_2", 0.3, team=True)],
            ["共鸣模态·聚爆时；集谐时的谐度破坏增幅不算"],
        ),
        "chain:1": OK,
        "chain:2:121101": (
            [V("dmg_2", 0.5, when=["聚爆"]), V("res_shred", 0.1, element=2)],
            ["简并虚质按满 10 层算"],
        ),
        "chain:2:121102": OK,
        "chain:3": (
            [
                V("mv", 0.8, kind="lib", skill="帷幕终景·幻灭之形"),
                V("mv", 12.0, skill="拟态泡泡·布景之形"),
                V("concerto", 30),
            ],
            ["【黯核】满时的倍率按共鸣技能算"],
        ),
        "chain:4": OK,
        "chain:5": OK,
        "chain:6": OK,
        "chain:6:121101": ([], ["聚爆效应的倍率提升：计算的异常效应伤害只算光噪"]),
        "chain:6:121102": OK,
        "inherent:1005305:1": OK,
        "outro:1005309": OK,
        "outro:1005309:2": OK,
    },
    "丽贝卡": {
        "inherent:1004804": ([V("atk_pct", 0.1, **S(2))], ["谐度破坏增幅不算"]),
        "inherent:1004805": OK,
        "chain:1": ([V("mv", 0.5, skill="猎手"), V("mv", 0.5, skill="铁胆")], []),
        "chain:2": (
            [V("dmg_all", 0.2, team=True), V("amplify", 0.15, team=True, when=["骇破响应"])],
            [],
        ),
        "chain:3": (
            [
                V("mv", 0.6, kind="lib", skill="狂欢时间！"),
                V("mv", 0.6, kind="lib", skill="大烟花！"),
            ],
            [],
        ),
        "chain:4": ([], ["小孩子才做选择！的加成原来是多少不知道，没算"]),
        "chain:5": OK,
        "chain:6": ([V("dmg_basic", 0.4)], ["普攻加成提升 40% 按加 40% 算"], [ROW("六链·额外伤害", "900.00%", "basic")]),  # noqa: E501
        "inherent:1004805:1": OK,
        "outro:1004809": (
            [V("amplify", 0.15), V("amplify", 0.35, kind="heavy")],
            ["超限按满 35% 算"],
        ),
        "chain:2:1": OK,
    },
    "洛瑟菈": {
        "inherent:1005004": OK,
        "inherent:1005004:110901": ([V("res_shred", 0.08, element=1, team=True)], []),
        "inherent:1005004:110902": OK,
        "inherent:1005005": OK,
        "chain:1": OK,
        "chain:2": OK,
        "chain:2:110901": OK,
        "chain:2:110902": OK,
        "chain:3": OK,
        "chain:4": OK,
        "chain:5": OK,
        "chain:6": ([V("final", 2.0, skill="断舍离", **S(3))], [FULL]),
        "inherent:1005004:1": ([V("res_shred", 0.08, element=1, team=True)], []),
        "inherent:1005004:2": OK,
        "skill:1005007:1": (
            [V("crit_dmg", 0.1, kind="echo", team=True, **S(4))],
            ["变焦按满 4 层算"],
        ),
        "outro:1005009": OK,
        "outro:1005009:2": OK,
        "chain:2:1": OK,
    },
    "露西": {
        "inherent:1004904": OK,
        "inherent:1004905": ([V("amplify", 0.25)], ["按两层【网络后门】算；骇破伤害的倍率不算"]),
        "chain:1": ([V("atk_pct", 0.2)], []),
        "chain:2": ([], [], [ROW("脉冲干扰·额外伤害", "450.00%", "heavy")]),
        "chain:3": (
            [V("mv", 0.5, skill="覆写篡改"), V("crit_dmg", 1.0, skill="覆写篡改")],
            ["欺骗程式和骇破响应的倍率不算：计算没有这一行"],
        ),
        "chain:4": OK,
        "chain:5": OK,
        "chain:6": ([V("final", 0.4, kind="heavy", when=["骇破响应"])], ["骇破伤害不算"]),
        "outro:1004909": OK,
        "chain:4:1": OK,
    },
    "绯雪": {
        "inherent:1005204": ([V("crit_dmg", 0.4)], ["霜冻效应的伤害：计算没有这一行"]),
        "inherent:1005205": OK,
        "chain:1": ([V("mv", 1.2, skill="预求身")], []),
        "chain:2": ([V("mv", 1.25, kind="basic", skill="居合")], []),
        "chain:3": (
            [
                V("mv", 1.6, kind="heavy", skill="寒簇·常世身"),
                V("mv", 1.6, kind="heavy", skill="枯霜·预求身"),
            ],
            ["额外异常倍率不算"],
        ),
        "chain:4": OK,
        "chain:5": ([V("mv", 0.8, skill=s) for s in ("常世身", "白玉切", "落华")], []),
        "chain:6": (
            [
                V("crit_dmg", 5.0, skill="预求我身·见心"),
                V("crit_dmg", 5.0, skill="预求我身·归刃"),
                V("crit_dmg", 0.4),
            ],
            ["霜冻效应的伤害：计算没有这一行"],
        ),
        "outro:1005209": ([V("amplify", 0.2, element=1, when=["霜渐"])], []),
        "chain:4:1": OK,
        "chain:6:1": ([], ["霜冻效应的伤害：计算没有这一行"]),
    },
    "漂泊者·导电": {
        "inherent:1005504": OK,
        "inherent:1005505": OK,
        "chain:1": OK,
        "chain:2": OK,
        "chain:3": OK,
        "chain:4": OK,
        "chain:5": ([V("crit_dmg", 0.2)], ["临界共鸣状态时"]),
        "chain:6": ([V("mv", 0.2, kind="skill", skill="千声翻涌"), V("mv", 0.2, skill="雷陨")], []),
        "skill:1005507:1": OK,
        "outro:1005509": (
            [V("amplify", 0.25, when=["光噪", "电磁", "聚爆", "虚湮", "霜渐", "风蚀"])],
            [],
        ),
    },
    "秧秧·玄翎": {
        "inherent:1005404": (
            [V("amplify", 0.3, when=["虚湮"]), V("amplify", 0.36, when=["虚湮"])],
            ["按目标 6 层虚湮效应算"],
        ),
        "inherent:1005405": OK,
        "chain:1": ([], [], [ROW("玄翎之影·抗坠", "337.98%", "heavy")]),
        "chain:2": (
            [
                V("final", 1.0, skill=s)
                for s in ("重击·苍剑式", "重击·羽剑式", "释羽风落", "湮象风华")
            ],
            [],
        ),
        "chain:3": OK,
        "chain:4": OK,
        "chain:5": OK,
        "chain:6": ([V("final", 0.4, kind="heavy")], [], [ROW("玄翎之影·止如槁木", "337.98%", "heavy")]),  # noqa: E501
        "outro:1005409": OK,
        "chain:4:1": OK,
    },
    "穗穗": {
        "inherent:1005704": (
            [
                V("crit", 0.8, skill="醒春潮"),
                V("crit", 0.8, skill="泠泠漱玉声"),
                V("dmg_1", 2.4, skill="醒春潮"),
                V("dmg_1", 2.4, skill="泠泠漱玉声"),
                V("concerto", 18),
                V("energy", 13),
            ],
            [],
        ),
        "inherent:1005705": OK,
        "chain:1": OK,
        "chain:2": (
            [V("crit_dmg", 0.5, team=True, when=["光噪", "电磁", "聚爆", "虚湮", "霜渐", "风蚀"])],
            [],
        ),
        "chain:3": ([V("concerto", 20)], []),
        "chain:4": ([V("heal", 0.5, skill="润物"), V("heal", 0.5, skill="春生")], []),
        "chain:5": ([V("mv", 1.0, skill="濯雨时")], []),
        "chain:6": (
            [V("crit_dmg", 5.0, skill="泠泠漱玉声"), V("crit_dmg", 5.0, skill="醒春潮")],
            [],
        ),
        "outro:1005709": OK,
        "outro:1005709:2": (
            [V("atk_pct", 0.5, needs={"stat": "er", "value": 2.6, "from": 2.0})],
            ["要消耗目标的异常效应层数"],
        ),
    },
    "清宵": {
        "inherent:1005804": OK,
        "inherent:1005805": (
            [V("final", 0.65, skill=s) for s in ("弦剑", "昙体仙身", "天光云影沧澜兴")],
            ["按 15 层心识锁定算"],
        ),
        "chain:1": ([V("crit", 0.16)], ["巨阙灭迹的伤害不算：计算没有这一行"]),
        "chain:2": ([V("mv", 0.4, kind="heavy", skill="弦剑")], []),
        "chain:3": (
            [
                V("crit_dmg", 1.0, kind="lib", skill="天光云影沧澜兴"),
                V("mv", 0.75, skill="天钧荡煞"),
            ],
            ["万物和鸣按 25 层算"],
        ),
        "chain:4": OK,
        "chain:5": ([V("mv", 1.0, kind="skill", skill="浮声一刹·行罚")], []),
        "chain:6": (
            [V("final", 0.4, skill=s) for s in ("弦剑", "天钧荡煞", "天光云影沧澜兴")],
            ["巨阙灭迹的部分不算"],
        ),
    },
    "心": {
        "inherent:1006104:131101": OK,
        "inherent:1006104:131102": (
            [V("dmg_3", 0.25, when=["电磁"], **S(2)), V("dmg_3", 0.2, when=["漂泊者·导电"])],
            [],
        ),
        "inherent:1006105:131101": OK,
        "inherent:1006105:131102": OK,
        "chain:1": OK,
        "chain:1:131101": (
            [V("mv", 0.55, kind="intro", skill="诸相同奏")],
            ["【同奏增益】按满 4 层算"],
        ),
        "chain:1:131102": OK,
        "chain:2": (
            [V("mv", 0.6, kind="heavy", skill=s) for s in ("步红尘", "镇红尘", "临寰宇", "镇寰宇")],
            [],
        ),
        "chain:3": ([V("mv", 0.7, kind="lib", skill="万阙垂天")], []),
        "chain:3:131101": (
            [V("crit_dmg", 0.8, kind="lib", skill="万阙垂天")],
            ["【同奏增益】按满 4 层算"],
        ),
        "chain:3:131102": OK,
        "chain:4": OK,
        "chain:5": OK,
        "chain:6": ([V("final", 0.4, kind="skill"), V("def_ignore", 0.2, kind="skill")], []),
        "chain:6:131101": OK,
        "chain:6:131102": OK,
        "outro:1006109": ([V("amplify", 0.2, when=["同奏"])], []),
        "outro:1006109:2": OK,
        "chain:4:1": OK,
    },
    "景燃": {
        "inherent:1005904": OK,
        "inherent:1005905": OK,
        "chain:1": (
            [V("mv", 0.8, kind="skill", skill=s) for s in ("阴蚀骨", "黄泉渡", "阳焚身", "往生送")],
            [],
        ),
        "chain:2": (
            [V("mv", 0.46, kind="heavy", skill="劫魄"), V("mv", 0.46, kind="heavy", skill="踏罡")],
            ["通幽每次进入战斗只有一次：没算"],
        ),
        "chain:3": ([V("atk", 2500, needs={"stat": "hp", "value": 50000, "from": 0.0})], []),
        "chain:4": OK,
        "chain:5": OK,
        "chain:6": ([V("final", 0.4, kind="heavy")], ["魑魅魍魉的伤害不算：计算没有这一行"]),
        "chain:4:1": OK,
    },
    "锁暝": {
        "inherent:1006204": ([V("dmg_3", 0.5), V("concerto", 10)], []),
        "inherent:1006205": (
            [V("mv", 1.0, kind="basic", skill="解伞形"), V("crit_dmg", 1.0)],
            ["按禁锁契主算：它和协契不同时在"],
        ),
        "chain:1": (
            [
                V("mv", 0.6, kind="intro", skill=s)
                for s in ("拢伞形·闪裂", "解伞形·碎霆", "拢伞形·锁妄念·同奏", "解伞形·旋雷破·同奏")
            ],
            [],
        ),
        "chain:2": (
            [V("crit_dmg", 0.4), V("crit_dmg", 0.34, others=True)],
            ["给下一位的按满 4 层【同奏增益】算"],
        ),
        "chain:3": OK,
        "chain:4": OK,
        "chain:5": ([V("mv", 0.4, kind="lib", skill="暝伞形·重锁狱瘴")], []),
        "chain:6": (
            [V("mv", 0.5, kind="basic", skill="暝伞形·刻心念"), V("crit_dmg", 2.0)],
            ["【同奏增益】效果提升的部分不算"],
        ),
        "inherent:1006205:1": ([V("dmg_3", 0.7)], ["按满 2 层【同奏增益】算"]),
        "outro:1006209": OK,
        "chain:2:1": ([V("crit_dmg", 0.34)], [FULL]),
    },
    "莉莉": {
        "inherent:1006304": ([V("concerto", 25)], []),
        "inherent:1006305": OK,
        "chain:1": OK,
        "chain:2": ([], ["【梦芳】层数不定：没算"]),
        "chain:3": ([V("concerto", 10), V("energy", 10)], []),
        "chain:4": OK,
        "chain:5": OK,
        "chain:6": (
            [
                V("dmg_5", 1.0, skill="梦之童话的落幕"),
                V("dmg_5", 1.0, skill="梦之魇影的终结"),
                V("dmg_5", 7.0, skill="永绽"),
            ],
            [],
        ),
        "outro:1006309": OK,
    },
}
