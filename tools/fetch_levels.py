# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Download the level EXP tables for resonators and weapons (D52).

Source: the game's own data tables as datamined in the public GitHub repository
Arikatsu/WutheringWaves_Data (BinData/). The Kuro wiki lists each EXP item's
value but no per-level table; the game data has both.

* role_level/rolelevelconsume.json -- ExpCount per level: the EXP to REACH that
  level (level 1 is 0). Three consume groups, identical today: one table is kept,
  and the tool fails if they ever differ.
* weapon/weaponlevel.json -- Exp per level, one table per LevelId (= rarity,
  weaponconf.json pairs LevelId with QualityId 1:1): the EXP to go from that
  level to the next (level 1 is not 0).
* weapon/weaponexpitem.json -- per 能源核心: its EXP and the 贝币 feeding it costs.
* phantom/phantomlevel.json -- per echo group (1-4 = 1..5-star: max +10, +15, +20,
  +25), the EXP to REACH each level (level 0 is 0). A 5-star echo 0 -> 25 = 142,600.

Checks on 3.6: resonator 1 -> 90 = 2,438,000 EXP; a 5-star weapon 1 -> 90 =
2,692,400 EXP.

Output: data/catalogue/levels.json. Run it again after a game patch (or from the
main app's 更新 page).

Run:  uv run python tools/fetch_levels.py [--branch 3.6]
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from collections import defaultdict
from pathlib import Path

REPO = "Arikatsu/WutheringWaves_Data"
RAW = "https://raw.githubusercontent.com/{repo}/{branch}/BinData/{path}"
API = "https://api.github.com/repos/{repo}"
OUT = Path("data/catalogue/levels.json")
UA = "wuwa-vision/0.1 (local inventory scanner; personal use)"


def _get(url: str) -> object:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def resonator_table(rows: list[dict]) -> list[int]:
    """EXP to reach each level, index = level (index 0 unused)."""
    groups: dict[int, dict[int, int]] = defaultdict(dict)
    for row in rows:
        groups[row["ConsumeGroupId"]][row["Level"]] = row["ExpCount"]
    tables = [[g.get(level, 0) for level in range(max(g) + 1)] for g in groups.values()]
    if any(t != tables[0] for t in tables):
        raise ValueError("resonator level groups differ: the planner needs a group per resonator")
    return tables[0]


def weapon_tables(rows: list[dict]) -> dict[str, list[int]]:
    """rarity -> EXP to go from each level to the next, index = level."""
    groups: dict[int, dict[int, int]] = defaultdict(dict)
    for row in rows:
        groups[row["LevelId"]][row["Level"]] = row["Exp"]
    return {str(k): [g.get(level, 0) for level in range(max(g) + 1)]
            for k, g in sorted(groups.items())}


def echo_tables(rows: list[dict]) -> dict[str, list[int]]:
    """echo group -> EXP to reach each level, index = level (0 = 0)."""
    groups: dict[int, dict[int, int]] = defaultdict(dict)
    for row in rows:
        groups[row["GroupId"]][row["Level"]] = row["Exp"]
    return {str(k): [g.get(level, 0) for level in range(max(g) + 1)]
            for k, g in sorted(groups.items())}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch", help="game version branch (default: the repo's default)")
    args = parser.parse_args()
    branch = args.branch or _get(API.format(repo=REPO))["default_branch"]  # type: ignore[index]

    def data(path: str) -> list[dict]:
        return _get(RAW.format(repo=REPO, branch=branch, path=path))  # type: ignore[return-value]

    resonator = resonator_table(data("role_level/rolelevelconsume.json"))
    weapon = weapon_tables(data("weapon/weaponlevel.json"))
    cores = data("weapon/weaponexpitem.json")
    echo = echo_tables(data("phantom/phantomlevel.json"))
    per_exp = {c["Cost"] / c["BasicExp"] for c in cores if c.get("BasicExp")}
    out = {
        "source": f"github.com/{REPO} ({branch}) BinData",
        "resonator": resonator,
        "weapon": weapon,
        "echo": echo,
        # 贝币 per weapon EXP fed (400 per 1000 today); one rate for every core
        "weapon_shells_per_exp": per_exp.pop() if len(per_exp) == 1 else None,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{branch}: resonator 1->90 = {sum(resonator[2:91]):,} EXP; "
          f"5-star weapon 1->90 = {sum(weapon.get('5', [])[1:90]):,} EXP; "
          f"top echo 0->{len(echo[max(echo)]) - 1} = {sum(echo[max(echo)]):,} EXP -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
