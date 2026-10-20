# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""The English name of everything the catalogue names (D163).

Source: the game's own text tables as datamined in the public GitHub repository
Arikatsu/WutheringWaves_Data, the same repository the level tables and the shops
come from (CREDITS.md):

* Textmaps/zh-Hans/multi_text/MultiText.json -- every text, Chinese, by key
* Textmaps/en/multi_text/MultiText.json -- the same keys, English

A name here is the Chinese text of some key; its English name is the English text
of that key. A name can be the text of many keys (an item's name, a line of dialogue,
a quest's title); the game's own name field for that kind of thing wins
(`ItemInfo_<id>_Name`, `WeaponConf_<id>_WeaponName`, `RoleInfo_<id>_Name`,
`ShopInfo_<id>_ShopName`, an area's or a country's title, a map mark's), then the
English text most of its keys share. Names whose keys disagree are listed under
`differs`, with every English text and how often, for a person to look at.

The 漂泊者 forms ("漂泊者-女-衍射") are built from the rover's, the element's and the
gender's English names. A name the tables do not have is left out: the 更新 page
lets a person give it one.

Writes data/catalogue/english.json: {"names": {name: English}, "differs": {...},
"missing": [...], "source", "fetched_at"}. Downloads about 100 MB; reads it once.

    uv run python tools/fetch_english.py [--branch BRANCH]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

REPO = "Arikatsu/WutheringWaves_Data"
RAW = "https://raw.githubusercontent.com/{repo}/{branch}/{path}"
API = "https://api.github.com/repos/{repo}"
TABLE = "Textmaps/{lang}/multi_text/MultiText.json"
CATALOGUE = Path("data/catalogue")
OUT = CATALOGUE / "english.json"
UA = "wuwa-vision/0.1 (local inventory scanner; personal use)"
_TAG = re.compile(r"</?\w+[^>]*>")
#: The game's own name fields, best first: a name's English is the one under these.
OWN = [re.compile(p) for p in (
    r"^ItemInfo_\d+_Name$", r"^WeaponConf_\d+_WeaponName$", r"^RoleInfo_\d+_Name$",
    r"^ShopInfo_\d+_ShopName$", r"^Country_\d+_Title$", r"^Area_\d+_Title$",
    r"^MapMark_\d+_MarkTitle$", r"^MonsterInfo_\d+_Name$")]
#: 漂泊者-女-衍射: the rover's forms, by gender and element.
_ROVER = re.compile(r"^漂泊者-(女|男)-(.+)$")
GENDER = {"女": "Female", "男": "Male"}


def plain(text: str | None) -> str:
    """A text as the game shows it, without its markup."""
    return _TAG.sub("", text or "").strip()


def rank(key: str) -> int:
    """How much a key's text is the thing's own name: 0 best."""
    return next((i for i, own in enumerate(OWN) if own.match(key)), len(OWN))


def pair(zh: dict[str, str], en: dict[str, str], wanted: set[str]) -> tuple[dict, dict]:
    """(names, differs): each wanted name -> its English, from the keys whose Chinese
    text it is; and the names whose keys gave more than one English text."""
    found: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for key, text in zh.items():
        name = plain(text)
        english = plain(en.get(key))
        if name in wanted and english:
            found[name].append((rank(key), english))
    names, differs = {}, {}
    for name, seen in found.items():
        best = min(r for r, _ in seen)
        top = Counter(e for r, e in seen if r == best)
        names[name] = sorted(top.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        every = Counter(e for _, e in seen)
        if len(every) > 1:
            differs[name] = dict(every.most_common())
    return names, differs


def rover_forms(wanted: set[str], names: dict[str, str]) -> dict[str, str]:
    """漂泊者-女-衍射 -> "Rover (Spectro, Female)", from the parts' English names."""
    out = {}
    rover = names.get("漂泊者")
    for name in wanted:
        form = _ROVER.match(name)
        if form and rover and names.get(form.group(2)):
            out[name] = f"{rover} ({names[form.group(2)]}, {GENDER[form.group(1)]})"
    return out


def wanted_names(directory: Path) -> set[str]:
    """Everything the catalogue names: items, dishes, resonators and weapons, shops
    and the names the wiki gives them, the countries and towns they are in, and the
    elements (for the rover's forms)."""
    out: set[str] = set()
    index = directory / "index.json"
    if index.exists():
        out |= {e["name"] for e in json.loads(index.read_text(encoding="utf-8")) if e.get("name")}
    builds = directory / "builds.json"
    if builds.exists():
        data = json.loads(builds.read_text(encoding="utf-8"))
        for kind in ("resonators", "weapons"):
            for name, build in (data.get(kind) or {}).items():
                out.add(name)
                if build.get("element"):
                    out.add(build["element"])
    shops = directory / "shops.json"
    if shops.exists():
        for shop in json.loads(shops.read_text(encoding="utf-8")).get("shops") or []:
            out |= {n for n in [shop.get("name"), *shop.get("also", [])] if n}
            for r in shop.get("regions") or []:
                out |= {w for w in (r.get("country"), r.get("town")) if w}
    out.add("漂泊者")
    return out


def _get(url: str) -> object:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=600) as response:
        return json.loads(response.read())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--branch", help="the repository's branch (default: its default branch)")
    args = parser.parse_args(argv)
    wanted = wanted_names(CATALOGUE)
    if len(wanted) < 10:
        print("no catalogue to name: run tools/fetch_catalogue.py first", file=sys.stderr)
        return 1
    branch = args.branch or _get(API.format(repo=REPO))["default_branch"]  # type: ignore[index]

    def text(lang: str) -> dict[str, str]:
        rows = _get(RAW.format(repo=REPO, branch=branch, path=TABLE.format(lang=lang)))
        return {row["Id"]: row["Content"] for row in rows}  # type: ignore[union-attr]

    print(f"English names for {len(wanted)} names, from {REPO} ({branch})")
    zh = text("zh-Hans")
    en = text("en")
    names, differs = pair(zh, en, wanted)
    del zh, en
    names.update(rover_forms(wanted, names))
    missing = sorted(wanted - set(names))
    OUT.write_text(json.dumps({
        "names": dict(sorted(names.items())), "differs": dict(sorted(differs.items())),
        "missing": missing, "source": f"github.com/{REPO} ({branch}) {TABLE}",
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"named {len(names)}; {len(differs)} with more than one English text; "
          f"{len(missing)} not in the tables: {', '.join(missing[:12])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
