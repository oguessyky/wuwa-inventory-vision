# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Every buff's words, read by hand, written to src/wuwa_vision/calc_judged.json: each weapon's
passive (D303), each echo set's pieces and each main echo (D305).

Each was read in full and judged: what it raises, for whom, under which condition, and what is
left out. A weapon's number is the passive's own at each rank (`param`: its {n}), so one reading
serves 精1 to 精5; a set's and an echo's words have their numbers filled in, so theirs are
written. Only a key of the words read is kept, not the game's words: `judge` uses a reading only
while the game's words still have that key.

The rules the readings follow:
- a condition met in any rotation (施放共鸣技能/变奏/共鸣解放, 普攻, 重击, 闪避, 登场, 受护盾)
  counts, at full stacks; one on HP (生命大于) counts as at full HP, 生命低于 does not;
- a condition on what the wielder applies is a `when` of the game's tags: a status effect
  (霜渐 …, 异常效应 any), a tuning (集谐/震谐/骇破, 谐度破坏技 any), 同奏, healing (生存治疗),
  or the one resonator named;
- 协奏能量 is `concerto`, 共鸣能量 `energy`, once a pass of the kit;
- given to the team, `team`; to the others only (an outro's gift), `others`;
- heals and shields the wielder gets, and what has no number in 计算, are `notes`.

Run:  uv run python tools/judged_buffs.py   (needs data/catalogue/calc.json, from 更新)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wuwa_vision import calc_data  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from judged_roles import KINDS, MODES, OK, ROLES  # noqa: E402

ANY = ["光噪", "电磁", "聚爆", "虚湮", "霜渐", "风蚀"]
#: Having a shield (D310): met by one whose kit shields themselves, or, in 配队, a member's.
SHIELDED = ["护盾"]
#: Who shields themselves in their kit (D310), read from their words: the rows of a shield are
#: found by the data; these give theirs by a skill's effect.
SHIELDS = ["桃祈", "鉴心", "奥古斯塔", "景燃", "尤诺", "夏空", "渊武"]
TUNE = ["集谐响应", "震谐响应", "骇破响应", "谐度破坏增幅"]
HEAL = ["生存治疗"]
SELF_HEAL = "回复自己生命：不是伤害，也不是治疗加成"


def P(stat: str, param: int, **more: object) -> dict:
    return {"stat": stat, "param": param, **more}


def S(n: int) -> dict:
    return {"per_stack": True, "stacks": n}


def plain_atk(i: int = 0) -> list[dict]:
    return [P("atk_pct", i)]


def V(stat: str, value: float, **more: object) -> dict:
    return {"stat": stat, "value": value, **more}


READ: dict[str, tuple[list[dict], list[str]]] = {
    # ---- 长刃 ----
    "千般渡": ([P("dmg_all", 0), P("crit_dmg", 3, **S(6)), P("crit", 11, kind="heavy"),
              P("def_ignore", 7, kind="heavy", **S(2))], ["【承天】【载物】按满层算"]),
    "宙算仪轨": ([P("def_pct", 0), P("concerto", 1), P("crit_dmg", 4, team=True, when=HEAL)], []),
    "时和岁稔": ([P("dmg_all", 0), P("dmg_skill", 1), P("dmg_skill", 3)], []),
    "昙切": ([P("atk_pct", 0), P("dmg_lib", 1, **S(3)), P("dmg_all", 4, team=True, when=ANY)],
           ["队伍的全属性加成：要附加异常效应"]),
    "浩境粼光": ([P("er", 0), P("dmg_lib", 1, **S(3))], []),
    "源能机锋": ([P("atk_pct", 0), P("dmg_lib", 1, when=["集谐响应"])], []),
    "焰痕": ([P("atk_pct", 0), P("dmg_lib", 1), P("dmg_2", 5, team=True)], []),
    "苍鳞千嶂": ([P("dmg_all", 0), P("dmg_heavy", 1, **S(2))], []),
    "驭冕铸雷之权": ([P("atk_pct", 0), P("dmg_heavy", 1),
                 P("def_ignore", 3, kind="heavy", when=SHIELDED, **S(5))],
                ["无视防御要有护盾，按满层算"]),
    "东落": ([P("atk_pct", 2, **S(4))], []),
    "凋亡频移": ([P("energy", 0), P("atk_pct", 1)], []),
    "容赦的沉思录": ([P("atk_pct", 0, **S(4), when=ANY)], []),
    "异响空灵": ([P("concerto", 0)], []),
    "永夜长明": ([P("atk_pct", 0), P("def_pct", 1)], []),
    "纹秋": ([P("atk_pct", 0, **S(5))], []),
    "重破刃-41型": ([P("atk_pct", 1)], ["按生命大于80%算", SELF_HEAL]),
    "金穹": ([P("atk_pct", 0), P("dmg_heavy", 1)], []),
    "戍关长刃·定军": ([P("dmg_basic", 0), P("dmg_heavy", 0)], []),
    "暗夜长刃·玄明": (plain_atk(), []),
    "源能长刃·测壹": ([], [SELF_HEAL]),
    "远行者长刃·辟路": ([P("energy", 0)], []),
    "钧天正音": ([P("concerto", 0), P("energy", 1)], []),
    "原初长刃·朴石": (plain_atk(), []),
    "教学长刃": (plain_atk(), []),
    # ---- 迅刀 ----
    "不屈命定之冠": ([P("hp_pct", 0), P("def_ignore", 1), P("amplify", 2, when=["风蚀"])], []),
    "不灭航路": ([P("crit", 0), P("dmg_basic", 1), P("dmg_basic", 3)], []),
    "云琅": ([P("atk_pct", 0), P("dmg_4", 1, **S(5), when=["集谐响应"]),
             P("def_ignore", 6, element=4, when=["集谐响应"])], []),
    "千古洑流": ([P("er", 0), P("atk_pct", 1, **S(2))], []),
    "天之苍苍": ([P("dmg_all", 0), P("amplify", 1, kind="heavy", when=["虚湮"]),
              P("def_ignore", 2, kind="heavy", when=["虚湮"])], []),
    "永远的启明星": ([P("dmg_all", 0), P("def_ignore", 1, kind="lib", when=["聚爆", "震谐响应"]),
                P("res_shred", 2, kind="lib", element=2, when=["聚爆", "震谐响应"])], []),
    "沉冥": ([P("atk_pct", 0), P("dmg_3", 1, when=["同奏"]), P("dmg_3", 5),
             P("dmg_3", 2, others=True, when=["同奏"])],
            ["【怅念】算给自己，【羁念】算给队友：两者不同时在"]),
    "灼霜": ([P("atk_pct", 0), P("amplify", 1, element=1, when=["霜渐"]),
             P("def_ignore", 2, kind="lib", when=["霜渐"]),
             P("amplify", 3, effect="霜渐", team=True, when=["霜渐"])], []),
    "血誓盟约": ([P("dmg_skill", 0, when=HEAL),
              P("amplify", 2, element=4, team=True, when=["漂泊者·气动"])], []),
    "裁春": ([P("atk_pct", 0), P("dmg_basic", 1, **S(3)), P("dmg_basic", 4)], []),
    "裁竹": ([P("atk_pct", 0), P("dmg_heavy", 2, scale=0.01, **S(2)),
             P("dmg_echo", 5, team=True)], []),
    "赫奕流明": ([P("atk_pct", 0), P("dmg_skill", 1, **S(14))], []),
    "镭射切变": ([P("atk_pct", 0), P("dmg_skill", 1, when=["集谐响应"])], []),
    "不归孤军": (plain_atk(), []),
    "心之锚": ([P("atk_pct", 3, **S(10)), P("crit", 7)], []),
    "永续坍缩": ([P("energy", 0), P("atk_pct", 1)], []),
    "瞬斩刀-18型": ([], ["生命低于一半时的重击加成不算", SELF_HEAL]),
    "翼锋": ([P("atk_pct", 0), P("dmg_lib", 1)], []),
    "行进序曲": ([P("concerto", 0)], []),
    "西升": ([P("atk_pct", 1, **S(6))], []),
    "风流的寓言诗": ([P("atk_pct", 0, **S(4), when=ANY)], []),
    "飞景": ([P("dmg_basic", 0), P("dmg_heavy", 0)], []),
    "戍关迅刀·镇海": ([P("dmg_skill", 0)], []),
    "暗夜迅刀·黑闪": (plain_atk(), []),
    "源能迅刀·测贰": ([], [SELF_HEAL]),
    "远行者迅刀·旅迹": ([P("energy", 0)], []),
    "原初迅刀·鸣雨": (plain_atk(), []),
    "教学迅刀": (plain_atk(), []),
    # ---- 佩枪 ----
    "停驻之烟": ([P("er", 0), P("atk_pct", 1, others=True)], []),
    "光影双生": ([P("atk_pct", 0), P("amplify", 1, kind="heavy"), P("amplify", 3, kind="echo"),
              P("def_ignore", 6)], []),
    "安魂": ([P("hp_pct", 0), P("concerto", 1), P("atk_pct", 3, team=True, when=HEAL),
             P("dmg_echo", 5, team=True, when=HEAL)], ["队伍的攻击：按队友有同奏算"]),
    "林间的咏叹调": ([P("atk_pct", 0), P("dmg_4", 1, when=["风蚀"]),
                P("res_shred", 3, element=4, team=True, when=["风蚀"])], []),
    "死与舞": ([P("atk_pct", 0), P("dmg_skill", 1)], []),
    "溢彩荧辉": ([P("atk_pct", 0), P("dmg_basic", 1),
              P("final", 3, team=True, when=["集谐响应", "震谐响应"], **S(3))], []),
    "相位涟漪": ([P("atk_pct", 0), P("dmg_all", 1, when=TUNE)], []),
    "碎骨": ([P("atk_pct", 0), P("dmg_basic", 1), P("dmg_basic", 3, when=["骇破响应"]),
             P("atk_pct", 5, team=True, when=["骇破响应"])], []),
    "蜃影": ([P("atk_pct", 0), P("dmg_5", 1, **S(2)),
             P("amplify", 4, kind="heavy", when=["骇破响应"]),
             P("def_ignore", 5, kind="heavy", scale=0.01, when=["骇破响应"])], []),
    "华彩乐段": ([P("concerto", 0)], []),
    "叙别的罗曼史": ([P("atk_pct", 0, **S(4), when=ANY)], []),
    "奔雷": ([P("dmg_skill", 0, **S(3))], []),
    "悖论喷流": ([P("energy", 0), P("atk_pct", 1)], []),
    "无眠烈火": ([P("dmg_skill", 0)], []),
    "穿击枪-26型": ([P("atk_pct", 1, **S(2))], ["按没有受到伤害算", SELF_HEAL]),
    "阳焰": ([P("atk_pct", 0, **S(4)), P("dmg_heavy", 0, **S(4))], []),
    "飞逝": ([P("atk_pct", 0, **S(3))], []),
    "戍关佩枪·平云": ([P("dmg_skill", 0)], []),
    "暗夜佩枪·暗星": (plain_atk(), []),
    "源能佩枪·测叁": ([], [SELF_HEAL]),
    "远行者佩枪·洞察": ([P("energy", 0)], []),
    "原初佩枪·穿林": (plain_atk(), []),
    "教学佩枪": (plain_atk(), []),
    # ---- 臂铠 ----
    "万物持存的注释": ([P("atk_pct", 0), P("dmg_lib", 1), P("def_ignore", 3, kind="lib", **S(5))],
                 ["无视防御按满层算：变奏时就是满层"]),
    "悲喜剧": ([P("atk_pct", 0), P("dmg_heavy", 1)], []),
    "擎渊怒涛": ([P("er", 0), P("dmg_basic", 1), P("dmg_skill", 3)], []),
    "昭日译注": ([P("atk_pct", 0), P("amplify", 1, kind="echo"),
              P("def_ignore", 3, element=4)], []),
    "焰光裁定": ([P("atk_pct", 0), P("def_ignore", 1), P("amplify", 2, effect="光噪")], []),
    "白昼之脊": ([P("atk_pct", 0), P("dmg_5", 1), P("amplify", 3, kind="basic", when=["集谐响应"]),
              P("def_ignore", 4, kind="basic", when=["集谐响应"])], []),
    "脉冲协臂": ([P("atk_pct", 0), P("dmg_basic", 1, **S(4), when=["集谐响应"])], []),
    "诸方玄枢": ([P("dmg_all", 0), P("dmg_lib", 1)], []),
    "凌空": ([P("atk_pct", 0), P("dmg_lib", 1)], []),
    "呼啸重音": ([P("concerto", 0)], []),
    "尘云旋臂": ([P("energy", 0), P("atk_pct", 1)], []),
    "袍泽之固": ([P("dmg_lib", 0)], []),
    "酩酊的英雄志": ([P("atk_pct", 0, **S(4), when=ANY)], []),
    "金掌": ([P("dmg_lib", 0)], []),
    "钢影拳-21丁型": ([P("atk_pct", 0), P("final", 1, skill="闪避反击")], [SELF_HEAL]),
    "骇行": ([P("atk_pct", 1, **S(3)), P("def_pct", 1, **S(3))], ["按没有受到伤害、满层算"]),
    "戍关臂铠·拔山": ([P("dmg_lib", 0)], []),
    "暗夜臂铠·夜芒": (plain_atk(), []),
    "源能臂铠·测肆": ([], [SELF_HEAL]),
    "远行者臂铠·破障": ([P("energy", 0)], []),
    "原初臂铠·磐岩": (plain_atk(), []),
    "教学臂铠": (plain_atk(), []),
    # ---- 音感仪 ----
    "和光回唱": ([P("atk_pct", 0), P("dmg_basic", 1, **S(3), when=["光噪"]),
              P("dmg_heavy", 1, **S(3), when=["光噪"]),
              P("amplify", 4, effect="光噪", team=True)], []),
    "存帧": ([P("atk_pct", 0), P("dmg_1", 1, when=["霜渐"]),
             P("atk_pct", 3, team=True, when=["霜渐"])], []),
    "幽冥的忘忧章": ([P("atk_pct", 0), P("dmg_skill", 2), P("amplify", 3, kind="echo"),
                P("def_ignore", 4)], []),
    "掣傀之手": ([P("dmg_all", 0), P("atk_pct", 1, **S(2)), P("atk_pct", 4)],
             ["不在场时的额外攻击按有算"]),
    "星序协响": ([P("hp_pct", 0), P("concerto", 1), P("atk_pct", 4, team=True, when=HEAL)], []),
    "栖霞饮露": ([P("hp_pct", 0), P("concerto", 1), P("atk_pct", 2, team=True, when=["霜渐"])],
             ["队伍的攻击：要附加霜渐效应，也要造成治疗"]),
    "海的呢喃": ([P("atk_pct", 0), P("dmg_basic", 6), P("res_shred", 8, element=6)], []),
    "漪澜浮录": ([P("er", 0), P("dmg_basic", 1, **S(5))], []),
    "玉阙玄华": ([P("dmg_all", 0), P("amplify", 1, kind="skill", when=["电磁", "同奏"]),
              P("res_shred", 2, kind="skill", element=3, when=["电磁", "同奏"]),
              P("amplify", 3, effect="电磁", team=True, when=["电磁", "同奏"])], []),
    "玻色星仪": ([P("atk_pct", 0), P("atk_pct", 1, when=TUNE), P("dmg_basic", 2, when=TUNE)], []),
    "琼枝冰绡": ([P("atk_pct", 0), P("dmg_basic", 5)],
             ["算的是不在场时的普攻加成：在场时的三层在延奏时换成它"]),
    "赝作的矮星": ([P("atk_pct", 0), P("dmg_lib", 1, when=["聚爆", "集谐响应"]),
               P("atk_pct", 3, team=True, when=["聚爆", "集谐响应"])], []),
    "今州守望": ([P("atk_pct", 0), P("hp_pct", 1)], []),
    "大海的馈赠": ([P("dmg_5", 0, **S(4), when=["光噪"])], []),
    "奇幻变奏": ([P("concerto", 0)], []),
    "异度": ([P("heal", 0, **S(3))], []),
    "曜光": ([P("atk_pct", 0), P("dmg_basic", 0)], []),
    "核熔星盘": ([P("energy", 0), P("atk_pct", 1)], []),
    "清音": (plain_atk(), []),
    "渊海回声": ([P("heal", 0)], []),
    "虚饰的华尔兹": ([P("atk_pct", 0, **S(4), when=ANY)], []),
    "鸣动仪-25型": ([P("atk_pct", 5)], ["按生命高于60%算", SELF_HEAL]),
    "戍关音感仪·留光": ([P("dmg_basic", 0), P("dmg_heavy", 0)], []),
    "暗夜矩阵·暝光": (plain_atk(), []),
    "源能音感仪·测五": ([], [SELF_HEAL]),
    "远行者矩阵·探幽": ([P("energy", 0)], []),
    "原初音感仪·听浪": (plain_atk(), []),
    "教学音感仪": (plain_atk(), []),
}


#: Each set's pieces past its 2-piece stat (D305), as (effects, notes).
SHIELD = "要有护盾：自己会上护盾，或配队里有人给；按满层算"
SETS: dict[str, dict[str, tuple[list[dict], list[str]]]] = {
    "凝夜白霜": {"5": ([V("dmg_1", 0.1, **S(3))], [])},
    "熔山裂谷": {"5": ([V("dmg_2", 0.3)], [])},
    "彻空冥雷": {"5": ([V("dmg_3", 0.15, **S(2))], [])},
    "啸谷长风": {"5": ([V("dmg_4", 0.3)], [])},
    "浮星祛暗": {"5": ([V("dmg_5", 0.3)], [])},
    "沉日劫明": {"5": ([V("dmg_6", 0.075, **S(4))], [])},
    "隐世回光": {"5": ([V("atk_pct", 0.15, team=True, when=HEAL)], [])},
    "轻云出月": {"5": ([V("atk_pct", 0.225, others=True)], ["给下一位登场的角色，不给自己"])},
    "不绝余音": {"5": ([V("atk_pct", 0.05, **S(4)), V("dmg_outro", 0.6)], [])},
    "凌冽决断之心": {"5": ([V("dmg_1", 0.225), V("dmg_skill", 0.18, **S(2))], [])},
    "此间永驻之光": {"5": ([V("crit", 0.2, when=["光噪"]), V("dmg_5", 0.15, when=["光噪"])], [])},
    "幽夜隐匿之帷": {"5": ([V("dmg_6", 0.15, others=True)],
                     ["延奏时额外 480% 湮灭伤害不算：计算没有这一行",
                      "湮灭加成给下一位登场的角色"])},
    "高天共奏之曲": {"5": ([V("final", 0.8, skill="协同攻击"),
                      V("atk_pct", 0.2, team=True, when=["协同攻击"])], [])},
    "无惧浪涛之勇": {"5": ([V("atk_pct", 0.15),
                      V("dmg_all", 0.3, needs={"stat": "er", "value": 2.5, "from": 2.4999})],
                     ["全属性加成要共鸣效率到 250%"])},
    "流云逝尽之空": {"5": ([V("dmg_4", 0.15, team=True, when=["风蚀"]),
                      V("dmg_4", 0.15, when=["风蚀"])], [])},
    "愿戴荣光之旅": {"5": ([V("crit", 0.1, when=["风蚀"]), V("dmg_4", 0.3, when=["风蚀"])], [])},
    "奔狼燎原之焰": {"5": ([V("dmg_2", 0.15, team=True), V("dmg_lib", 0.2)], [])},
    "失序彼岸之梦": {"3": ([V("crit", 0.2), V("dmg_echo", 0.35)], ["按共鸣能量为 0 时算"])},
    "荣斗铸锋之冠": {"3": ([V("atk_pct", 0.06, when=SHIELDED, **S(5)),
                       V("crit_dmg", 0.04, when=SHIELDED, **S(5))], [SHIELD])},
    "息界同调之律": {"3": ([V("dmg_heavy", 0.3), V("dmg_echo", 0.04, team=True, **S(4))], [])},
    "焚羽猎魔之影": {"3": ([V("crit", 0.2, kind="heavy"), V("crit", 0.2, kind="echo"),
                      V("dmg_2", 0.16)], [])},
    "命理崩毁之弦": {"3": ([V("atk_pct", 0.2, when=["虚湮"]),
                       V("dmg_lib", 0.3, when=["虚湮"])], [])},
    "逆光跃彩之约": {"5": ([V("atk_pct", 0.15, others=True)],
                     ["给下一位登场的角色；随它的谐度破坏增幅额外加的部分不算"])},
    "星构寻辉之环": {"5": ([V("atk_pct", 0.25, team=True, when=HEAL,
                        needs={"stat": "tune_eff", "value": 1.25, "from": 0.0})], [])},
    "流金溯真之式": {"5": ([V("dmg_5", 0.1, **S(3)), V("dmg_basic", 0.4)], [])},
    "长路启航之星": {"5": ([V("crit", 0.2, when=["聚爆", "震谐响应"]),
                      V("dmg_2", 0.2, when=["聚爆", "震谐响应"])], [])},
    "斑驳粉饰之沫": {"5": ([V("dmg_2", 0.1, when=["聚爆"]),
                       V("dmg_2", 0.25, others=True, when=["聚爆"])],
                     ["25% 给下一位登场的角色"])},
    "听唤语义之愿": {"5": ([V("crit", 0.2, kind="echo"), V("dmg_4", 0.15)], [])},
    "雪落无声之愿": {"5": ([V("dmg_1", 0.1, when=["霜渐"]), V("crit", 0.25, when=["霜渐"])],
                     ["【落雪】按共鸣解放时用掉算：给下一位的冷凝加成和它只能有一个"])},
    "剪心辑梦之影": {"5": ([], ["谐度破坏增幅不算：计算还没有谐度破坏"])},
    "碎梦亡鬼之魇": {"1": ([V("dmg_basic", 0.35, when=["骇破响应"]),
                      V("dmg_heavy", 0.35, when=["骇破响应"])], [])},
    "羽落空尘之歌": {"5": ([V("crit", 0.2, when=["虚湮"]), V("dmg_heavy", 0.35, when=["虚湮"]),
                      V("atk_pct", 0.25, team=True, when=["霜渐"],
                        needs={"stat": "er", "value": 2.5, "from": 0.0})], [])},
    "清邪荡煞之心": {"5": ([V("crit_dmg", 0.2, when=["集谐响应"]),
                      V("dmg_4", 0.3, when=["集谐响应"])], [])},
    "冥途夜行之灯": {"5": ([V("crit", 0.05, when=SHIELDED, **S(4)), V("dmg_2", 0.15, when=SHIELDED)],  # noqa: E501
                     [SHIELD])},
    "衔梦照世之心": {"5": ([V("crit", 0.15, when=["电磁", "同奏"]),
                      V("dmg_3", 0.225, when=["电磁", "同奏"])], [])},
    "镜影流电之瞬": {"5": ([V("dmg_3", 0.1, when=["电磁"]),
                       V("dmg_3", 0.25, others=True, when=["电磁"])],
                     ["25% 给下一位登场的角色"])},
    "茜染怀想之花": {"5": ([V("atk_pct", 0.1, team=True, when=HEAL),
                      V("atk_pct", 0.15, team=True, when=["同奏"])],
                     ["额外 15% 按队伍里有同奏的角色算"])},
}


def _two(stat: str, kind: str) -> list[dict]:
    return [V(stat, 0.12), V(kind, 0.12)]


SUMMON = "召唤出来的伤害不算：计算没有这一行"
#: Each main echo's buff when worn first (D305).
ECHOES: dict[str, tuple[list[dict], list[str]]] = {
    "毒冠贵族": ([V("dmg_1", 0.12)], []),
    "琉璃刀伶": ([V("dmg_3", 0.12)], []),
    "罗蕾莱": (_two("dmg_6", "dmg_basic"), []),
    "异构武装": (_two("dmg_1", "dmg_skill"), []),
    "叹息古龙": (_two("dmg_2", "dmg_basic"), []),
    "赫卡忒": ([V("final", 0.4, skill="协同攻击")], []),
    "梦魇·飞廉之猩": (_two("dmg_4", "dmg_heavy"), []),
    "梦魇·无常凶鹭": (_two("dmg_6", "dmg_heavy"), []),
    "梦魇·云闪之鳞": (_two("dmg_3", "dmg_lib"), []),
    "梦魇·朔雷之鳞": (_two("dmg_3", "dmg_skill"), []),
    "梦魇·无冠者": (_two("dmg_6", "dmg_basic"), []),
    "梦魇·燎照之骑": (_two("dmg_2", "dmg_skill"), []),
    "梦魇·哀声鸷": ([V("dmg_5", 0.12)], []),
    "梦魇·辉萤军势": ([V("dmg_1", 0.12), V("final", 0.3, skill="协同攻击")], []),
    "荣光节使": (_two("dmg_5", "dmg_heavy"), []),
    "共鸣回响·芙露德莉斯": ([V("dmg_4", 0.1),
                         V("dmg_4", 0.1, when=["漂泊者·气动", "卡提希娅"])], []),
    "角鳄": (_two("dmg_4", "dmg_lib"), []),
    "梦魇·凯尔匹": (_two("dmg_1", "dmg_4"), [SUMMON]),
    "荣耀狮像": (_two("dmg_2", "dmg_lib"), []),
    "梦魇·赫卡忒": ([V("dmg_6", 0.12), V("dmg_echo", 0.2)], []),
    "共鸣回响·芬莱克": (_two("dmg_4", "dmg_heavy"), []),
    "蚀脊龙": ([V("dmg_2", 0.12), V("dmg_echo", 0.2)], []),
    "伪作的神王": (_two("dmg_3", "dmg_heavy"), [SUMMON]),
    "海之女": (_two("dmg_4", "dmg_lib"), []),
    "共鸣回响·鸣式·利维亚坦": (_two("dmg_6", "dmg_lib"), []),
    "双极·星升辉铳": (_two("dmg_5", "dmg_basic"), []),
    "双极·渊陨重锋": (_two("dmg_3", "dmg_basic"), []),
    "炉芯机骸": ([V("er", 0.1)], []),
    "辛吉勒姆": ([V("dmg_lib", 0.25, when=["爱弥斯"])], []),
    "无铭探索者": ([V("dmg_4", 0.12), V("dmg_echo", 0.2)], []),
    "异相·无妄者": (_two("dmg_2", "dmg_skill"), []),
    "异相·琉璃刀伶": ([V("dmg_3", 0.12)], []),
    "异相·异构武装": (_two("dmg_1", "dmg_skill"), []),
    "异相·罗蕾莱": (_two("dmg_6", "dmg_basic"), []),
    "异相·荣光节使": (_two("dmg_5", "dmg_heavy"), []),
    "异相·梦魇·无冠者": (_two("dmg_6", "dmg_basic"), []),
    "异相·梦魇·燎照之骑": (_two("dmg_2", "dmg_skill"), []),
    "异相·角鳄": (_two("dmg_4", "dmg_lib"), []),
    "异相·伪作的神王": (_two("dmg_3", "dmg_heavy"), [SUMMON]),
    "异相·双极·星升辉铳": (_two("dmg_5", "dmg_basic"), []),
    "异相·双极·渊陨重锋": (_two("dmg_3", "dmg_basic"), []),
    "异相·辛吉勒姆": ([V("dmg_lib", 0.25, when=["爱弥斯"])], []),
    "今汐": ([V("final", 0.4, skill="协同攻击")], []),
    "共鸣回响·鸣式·虚造神型": (_two("dmg_1", "dmg_lib"), []),
    "异相·炉芯机骸": ([V("er", 0.1)], []),
    "共鸣回响·梦魇亚当·重锤": ([V("crit", 0.15, when=["露西", "丽贝卡"])],
                          ["换成的特殊声骸技能不算"]),
    "封庭械囿": ([V("heal", 0.1)], []),
    "万囮牢·朽躯": (_two("dmg_2", "dmg_heavy"), []),
    "千傀重楼": (_two("dmg_6", "dmg_heavy"), []),
    "异相·封庭械囿": ([V("heal", 0.1)], []),
    "天傀劫煞": ([V("dmg_4", 0.1), V("dmg_4", 0.1, when=["集谐响应"])], []),
    "异相·万囮牢·朽躯": (_two("dmg_2", "dmg_heavy"), []),
    "解形煞": ([V("er", 0.1)], []),
    "共鸣回响·天演溯心": ([V("dmg_3", 0.1), V("dmg_3", 0.1, when=["电磁", "同奏"])], []),
}


def _sets(data: dict) -> dict:
    out: dict[str, dict] = {}
    for name, entry in data["sets"].items():
        texts = entry.get("text") or {}
        asked = {p for p in texts if not (p == "2" and entry.get("two"))}
        read = SETS.get(name, {})
        if asked != set(read):
            sys.exit(f"set {name}: pieces {sorted(asked)}, read {sorted(read)}")
        out[name] = {p: {"key": calc_data.words_key(texts[p]), "effects": e,
                         **({"notes": n} if n else {})} for p, (e, n) in sorted(read.items())}
    if set(SETS) - set(out):
        sys.exit(f"sets not in the data: {sorted(set(SETS) - set(out))}")
    return out


def _echoes(data: dict) -> dict:
    mains = {n: e["main_buff"] for n, e in data["echoes"].items() if e.get("main_buff")}
    if set(mains) != set(ECHOES):
        sys.exit(f"main echoes not read: {sorted(set(mains) - set(ECHOES))}; "
                 f"not in the data: {sorted(set(ECHOES) - set(mains))}")
    return {n: {"key": calc_data.words_key(mains[n]["text"]), "effects": e,
                **({"notes": notes} if notes else {})} for n, (e, notes) in sorted(ECHOES.items())}


#: The sets the game recommends that its own tables do not have (D310), as the game shows them.
RECOMMENDED: dict[str, list[str]] = {
    # the user, 2026-11-14: in the game it shows 愿戴, 隐世回光, 流云逝尽之空
    "漂泊者·气动": ["隐世回光", "流云逝尽之空", "愿戴荣光之旅"],
}


def _roles(data: dict) -> dict:
    """Each resonator's buffs and gifts (D306), by id: a reading for each paragraph under it."""
    out: dict[str, dict] = {}
    for name, role in data["roles"].items():
        read = ROLES.get(name)
        if read is None:
            sys.exit(f"resonator not read: {name}")
        listed = [*(role.get("buffs") or []), *(role.get("gives") or [])]
        ids = {b["id"] for b in listed}
        if set(read) != ids:
            sys.exit(f"{name}: not read {sorted(ids - set(read))}; not in the data "
                     f"{sorted(set(read) - ids)}")
        mine: dict[str, list] = {}
        for buff in listed:
            said = read[buff["id"]]
            text, title = buff.get("text") or "", buff.get("title") or ""
            if said == OK:
                # the reader's rows, as it reads them (D316)
                effects, notes, rows = buff.get("effects") or [], [], calc_data.rows_of(text, title)
            else:
                effects, notes, *more = said
                rows = more[0] if more else calc_data.rows_of(text, title)
            mine.setdefault(buff["id"], []).append(
                {"key": calc_data.words_key(text), "effects": effects,
                 **({"notes": notes} if notes else {}), **({"rows": rows} if rows else {})})
        out[name] = mine
    if set(ROLES) - set(data["roles"]):
        sys.exit(f"resonators not in the data: {sorted(set(ROLES) - set(data['roles']))}")
    return out


def main() -> None:
    data = json.loads((ROOT / "data" / "catalogue" / calc_data.NAME).read_text(encoding="utf-8"))
    weapons = data["weapons"]
    missing = sorted(set(weapons) - set(READ))
    unknown = sorted(set(READ) - set(weapons))
    if missing or unknown:
        sys.exit(f"not read: {missing}; not in the data: {unknown}")
    out = {}
    for name in sorted(READ):
        effects, notes = READ[name]
        params = weapons[name].get("params") or []
        for effect in effects:
            if "param" in effect and effect["param"] >= len(params):
                sys.exit(f"{name}: no {{{effect['param']}}}")
        out[name] = {"key": calc_data.words_key(weapons[name]["text"]), "effects": effects,
                     **({"notes": notes} if notes else {})}
    old = json.loads(calc_data.JUDGED_PATH.read_text(encoding="utf-8"))
    old["weapons"] = out
    old["sets"] = _sets(data)
    old["echoes"] = _echoes(data)
    old["roles"] = _roles(data)
    for name, sets in RECOMMENDED.items():
        if name not in data["roles"] or set(sets) - set(data["sets"]):
            sys.exit(f"recommended: {name} {sets} not in the data")
    old["recommended"] = RECOMMENDED
    if set(SHIELDS) - set(data["roles"]):
        sys.exit(f"shields: not in the data {sorted(set(SHIELDS) - set(data['roles']))}")
    old["shields"] = SHIELDS
    if set(MODES) - set(data["roles"]):
        sys.exit(f"modes: not in the data {sorted(set(MODES) - set(data['roles']))}")
    old["modes"] = MODES
    if set(KINDS) - set(data["roles"]):
        sys.exit(f"kinds: not in the data {sorted(set(KINDS) - set(data['roles']))}")
    old["kinds"] = KINDS
    calc_data.JUDGED_PATH.write_text(
        json.dumps(old, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    texts = sum(len(v) for r in old["roles"].values() for v in r.values())
    print(f"read by hand: {len(out)} weapons, {len(old['sets'])} sets, "
          f"{len(old['echoes'])} main echoes, {len(old['roles'])} resonators ({texts} texts)")


if __name__ == "__main__":
    main()
