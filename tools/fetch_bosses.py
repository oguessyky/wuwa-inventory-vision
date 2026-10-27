# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Download the portraits of the bosses that drop build materials (D54).

The materials say who drops them ("哀声鸷的掉落物"); the pages show that boss as
an icon instead of a name. Source: Kuro's wiki enemy list (catalogue 1158, the
same API as tools/fetch_catalogue.py), each entry's square portrait, resized to
WebP by the wiki's CDN.

Drop names and enemy names differ a little: "岁主「角」" is the enemy "角",
"无冠者分身" is "无冠者", and the wiki writes "万囤牢" once for "万囮牢" -- matched
exactly, then by one name containing the other, then one character off.

Output: data/catalogue/bosses/<entry id>.webp and data/catalogue/bosses.json
{drop name: file}. Incremental: files on disk are not downloaded again.

Run:  uv run python tools/fetch_bosses.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import fetch_pool
from fetch_builds import _download
from fetch_recipes import _post

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

ENEMIES = 1158
OUT = Path("data/catalogue/bosses")
INDEX = Path("data/catalogue/bosses.json")
ICON_WIDTH = 160
DELAY_SECONDS = 0.3


def drops() -> set[str]:
    """Every boss the catalogue names as a drop source."""
    from wuwa_vision.catalogue import Catalogue
    from wuwa_vision.materials import role_of, targets

    catalogue = Catalogue.load()
    return {drop for name in targets(catalogue) if (drop := role_of(catalogue, name)[1])}


def match(drop: str, enemies: dict[str, dict]) -> str | None:
    if drop in enemies:
        return drop
    quoted = re.search(r"「(.+?)」", drop)  # 岁主「角」: the name in the brackets
    if quoted and quoted.group(1) in enemies:
        return quoted.group(1)
    inside = [e for e in enemies if len(e) > 1 and (e in drop or drop in e)]
    if len(inside) == 1:
        return inside[0]
    from wuwa_vision.recognize.names import snap

    snapped = snap(drop, frozenset(enemies))
    return snapped if snapped in enemies else None


def main() -> int:
    records = _post("getPage", {"catalogueId": ENEMIES, "page": 1, "limit": 1000})
    enemies = {r["name"].strip(): r for r in records["results"]["records"] if r.get("name")}
    OUT.mkdir(parents=True, exist_ok=True)
    index: dict[str, str] = {}
    missing = []
    jobs = []
    for drop in sorted(drops()):
        name = match(drop, enemies)
        record = enemies.get(name) if name else None
        url = ((record or {}).get("content") or {}).get("contentUrl")
        if not url:
            missing.append(drop)
            continue
        jobs.append((drop, url, f"{record['id']}.webp"))
    # a few at a time (D202), kept in the order asked, as before
    got: dict[str, str] = {}
    for (drop, _url, _file), saved, error in fetch_pool.each(
            jobs, lambda job: _download(job[1], OUT / job[2], ICON_WIDTH), pause=DELAY_SECONDS):
        if error is not None:
            raise error
        got[drop] = saved
    index.update((drop, got[drop]) for drop, _url, _file in jobs)
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    gaps = f"; not found: {', '.join(missing)}" if missing else ""
    print(f"{len(index)} boss icons -> {OUT}{gaps}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
