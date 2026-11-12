# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Download what 计算 needs (D268): skill multipliers, base stats, weapons, echoes and sets.

Source: the game's own data tables as datamined in the public GitHub repository
Arikatsu/WutheringWaves_Data (D149), on the branch of the newest game version. The tables
are listed in `wuwa_vision.calc_data.TABLES`; `calc_data.build` cuts them to one file.

Run from the main app's 更新 page (D46) -- only when its button is pressed -- or by hand.
Nothing is fetched when the file is already from the newest version, unless --force.

Output: data/catalogue/calc.json.

Run:  uv run python tools/fetch_calc.py [--branch 3.8] [--force]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wuwa_vision import calc_data  # noqa: E402

REPO = "Arikatsu/WutheringWaves_Data"
RAW = "https://raw.githubusercontent.com/{repo}/{branch}/{path}"
API = "https://api.github.com/repos/{repo}"
OUT = Path("data/catalogue") / calc_data.NAME
UA = "wuwa-vision/0.1 (local inventory scanner; personal use)"


def _get(url: str) -> object:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch", help="game version branch (default: the repo's default)")
    parser.add_argument("--force", action="store_true", help="fetch even when up to date")
    args = parser.parse_args()
    branch = args.branch or _get(API.format(repo=REPO))["default_branch"]  # type: ignore[index]
    have = calc_data.load(OUT.parent)
    if have and have.get("version") == branch and not args.force:
        print(f"{branch}: 计算's data is up to date -> {OUT}")
        return 0
    tables = {}
    for name, path in calc_data.TABLES.items():
        print(f"  {name} ...", flush=True)
        tables[name] = _get(RAW.format(repo=REPO, branch=branch, path=path))
    data = calc_data.build(tables, branch)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(
        f"{branch}: {len(data['roles'])} resonators, {len(data['weapons'])} weapons, "
        f"{len(data['sets'])} sets -> {OUT}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
