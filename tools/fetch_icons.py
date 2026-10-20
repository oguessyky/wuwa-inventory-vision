# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Download resonator head icons, the element icons and the 贝币 icon (D49, D133).

Source: Kuro's own wiki (库街区 鸣潮WIKI, wiki.kurobbs.com), and nothing else.

* Head icons: the wiki's 头像 catalogue (1363) lists the game's own avatars by
  name -- one per resonator, under the resonator's name, plus 女漂泊者 and
  男漂泊者 for the player character. Every 头像 whose name is a resonator's
  (catalogue 1105) is taken; the event avatars in the same list are not.
* Element icons: the six pictures the wiki's own 共鸣者 list draws on its cards.
  They are files of the wiki's pages, named in one of its scripts beside the
  table that says which number is which; the list says each resonator's number
  (`skillAttr`), and their pages say the element, so which picture is which
  element is read from the wiki, not assumed here.
* 贝币: its entry in the 特殊道具 catalogue (1223).

Not here, because the wiki does not have them:

* Weapon-type icons. The app ships its own five drawings
  (src/wuwa_vision/web/static/icons/, `catalogue.WEAPON_TYPE_ICONS`).
* The game's ids for resonators and weapons, which a pull export names its
  pulls by (D53). None are fetched, and a list an earlier version of this tool
  fetched is dropped from avatars.json by this run: the import now goes by the
  names shipped with the app and the ones the user gives (PLAN.md D133, D135).

Until D133 this tool read wuwatracker.com. That site's terms do not allow
collecting from it without written consent, so it is no longer asked anything.
Files an earlier run took from it are removed once this run has replaced them.

Output: data/catalogue/avatars/<file>.webp and data/catalogue/avatars.json
{"resonators": {name: file}, "elements": {中文: file}, "currency": {"贝币": file}}.

Scope and handling as tools/fetch_catalogue.py: Kuro Games' art, local display
only, never redistributed; gitignored data/, one-time setup (or the main app's
更新 page), serialised requests with a delay. Incremental: files already on
disk are not downloaded again.

Run:  uv run python tools/fetch_icons.py
"""

from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path

from fetch_builds import _download, _fetch
from fetch_recipes import _post

RESONATORS, HEADS, SPECIAL = 1105, 1363, 1223
#: The wiki's 共鸣者 list: the page whose scripts name the element pictures.
LIST_PAGE = "https://wiki.kurobbs.com/mc/catalogue/list?fid=1099&sid=1105"
ASSETS = "https://wiki.kurobbs.com/resource/wiki/prod/assets/"
OUT = Path("data/catalogue/avatars")
INDEX = Path("data/catalogue/avatars.json")
BUILDS = Path("data/catalogue/builds.json")
DELAY_SECONDS = 0.3
HEAD_WIDTH, ICON_WIDTH = 256, 128
#: How many of the wiki's scripts to look through for the element pictures.
MAX_SCRIPTS = 30
ROVER_FILES = {"女漂泊者": "rover-f.webp", "男漂泊者": "rover-m.webp"}
COIN = "贝币"
#: The element pictures by the name the wiki's files give them, for when the
#: numbered table cannot be read. 冷凝 is "bingning" and 湮灭 "jielin" there.
PINYIN = {"bingning": "冷凝", "rerong": "热熔", "daodian": "导电", "qidong": "气动",
          "yanshe": "衍射", "jielin": "湮灭"}
#: `x=new URL("…/ico-catalog-role-attr-<name>-<hash>.png",…)`
_ATTR_FILE = re.compile(r'(\w+)=new URL\("[^"]*?(ico-catalog-role-attr-([a-z]+)-[0-9a-f]+\.png)"')
#: `{2:bi,3:ki,4:hi,5:_i,6:wi,7:yi}`: skillAttr -> the variable above.
_ATTR_TABLE = re.compile(r"\{((?:\d+:[\w$]+,){3,}\d+:[\w$]+)\}")
_SCRIPT = re.compile(r'(?:src|href)="([^"]+\.js)"')
#: Another of the wiki's scripts, named anywhere in one of them: "catalog-editer-841e5a48.js".
_IMPORT = re.compile(r"[\w.\-]+-[0-9a-f]{8}\.js")


def records(catalogue_id: int) -> list[dict]:
    page = _post("getPage", {"catalogueId": catalogue_id, "page": 1, "limit": 1000})
    return page["results"]["records"]


def heads(avatars: list[dict], resonators: set[str]) -> dict[str, tuple[str, str]]:
    """name -> (picture url, file name), for every 头像 that is a resonator's."""
    found: dict[str, tuple[str, str]] = {}
    for record in avatars:
        name = (record.get("name") or "").strip()
        url = (record.get("content") or {}).get("contentUrl")
        if not url or not (name in resonators or name in ROVER_FILES):
            continue
        file = ROVER_FILES.get(name) or f"r-{record['id']}.webp"
        found.setdefault(name, (url, file))
    return found


def element_files(script: str) -> dict[str, str]:
    """skillAttr number (or, failing that, the file's own name) -> picture file,
    from the script of the wiki that names them."""
    files = {var: (file, key) for var, file, key in _ATTR_FILE.findall(script)}
    if not files:
        return {}
    for table in _ATTR_TABLE.findall(script):
        pairs = dict(pair.split(":") for pair in table.split(","))
        if set(pairs.values()) <= set(files):
            return {number: files[var][0] for number, var in pairs.items()}
    return {key: file for file, key in files.values()}


def elements_by_number(listed: list[dict], builds: dict) -> dict[str, str]:
    """skillAttr number -> element, as the wiki's own list and pages pair them."""
    votes: dict[str, Counter] = {}
    people = builds.get("resonators") or {}
    for record in listed:
        number = str((record.get("content") or {}).get("skillAttr") or "")
        element = (people.get(record.get("name")) or {}).get("element")
        if number and element:
            votes.setdefault(number, Counter())[element] += 1
    return {number: count.most_common(1)[0][0] for number, count in votes.items()}


def find_element_script() -> str:
    """The script of the wiki's list page that names the element pictures ('' if none)."""
    html = _fetch(LIST_PAGE).decode("utf-8", "replace")
    queue = [s if s.startswith("http") else ASSETS + s.rsplit("/", 1)[-1]
             for s in _SCRIPT.findall(html)]
    seen: set[str] = set()
    while queue and len(seen) < MAX_SCRIPTS:
        url = queue.pop(0)
        if url in seen or not url.startswith(ASSETS):
            continue
        seen.add(url)
        try:
            script = _fetch(url).decode("utf-8", "replace")
        except OSError:
            continue
        if element_files(script):  # the name alone is not enough: the main script lists every icon
            return script
        more = [ASSETS + name for name in dict.fromkeys(_IMPORT.findall(script))]
        # the catalogue's own scripts first: that is where the pictures are named
        first = [u for u in more if "catalog" in u]
        queue = first + queue + [u for u in more if u not in first]
        time.sleep(DELAY_SECONDS)
    return ""


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    old = json.loads(INDEX.read_text(encoding="utf-8")) if INDEX.exists() else {}
    builds = json.loads(BUILDS.read_text(encoding="utf-8")) if BUILDS.exists() else {}
    listed = records(RESONATORS)
    time.sleep(DELAY_SECONDS)
    people = heads(records(HEADS), {r["name"] for r in listed})
    time.sleep(DELAY_SECONDS)
    coin = next((r for r in records(SPECIAL) if r.get("name") == COIN), None)
    script = find_element_script()
    by_number = elements_by_number(listed, builds)
    icons = {}
    for key, file in element_files(script).items():
        if element := by_number.get(key) or PINYIN.get(key):
            icons[element] = file
    print(f"{len(people)} head icons, {len(icons)} element icons on the wiki", flush=True)

    # no "gids": the id list an earlier version fetched is not carried over (D135)
    index: dict = {"resonators": {}, "elements": {}, "currency": {}}
    jobs: list[tuple[str, Path, int, tuple[str, str]]] = [
        (url, OUT / file, HEAD_WIDTH, ("resonators", name))
        for name, (url, file) in sorted(people.items())]
    for element, file in sorted(icons.items()):
        key = file.split("-")[-2]
        dest = OUT / f"el-{key}.webp"
        jobs.append((ASSETS + file, dest, ICON_WIDTH, ("elements", element)))
    if coin and (coin.get("content") or {}).get("contentUrl"):
        url = coin["content"]["contentUrl"]
        jobs.append((url, OUT / "coin.webp", ICON_WIDTH, ("currency", COIN)))
    fetched = failed = 0
    for url, dest, width, (table, name) in jobs:
        try:
            had = dest.exists() and dest.stat().st_size > 0
            index[table][name] = _download(url, dest, width)
            if not had:
                fetched += 1
                time.sleep(DELAY_SECONDS)
        except OSError as exc:
            print(f"  FAILED {name}: {exc}", flush=True)
            failed += 1
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    removed = 0
    if failed == 0:
        # what an earlier run listed and this one does not: files from the old source
        kept = {file for table in ("resonators", "elements", "currency")
                for file in index[table].values()}
        for table in ("resonators", "elements", "weapons", "currency"):
            for file in (old.get(table) or {}).values():
                if file not in kept and (OUT / file).is_file():
                    (OUT / file).unlink()
                    removed += 1
    print(f"downloaded={fetched} failed={failed} removed={removed} -> {OUT}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
