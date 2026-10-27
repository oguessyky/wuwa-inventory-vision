# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Download cooking and crafting data: what each dish needs, and where each 食谱 is.

Source: Kuro's wiki (wiki.kurobbs.com), the same API as tools/fetch_catalogue.py.
Each entry page's "基础信息" block is a table of label/value rows (labels in
<th> on some pages, <td><strong> on others). Two categories:

* 可合成道具 (craftable: dishes, potions) -- 类型, 功能, 品质, 描述, 所需材料
  (ingredient x amount), 熟练度, 获取途径, 食谱解锁 (the 食谱 that teaches it).
* 道具合成图纸 (食谱 for dishes, 配方 for potions) -- 类型, 说明, 品质, 描述,
  获取途径 (where the 食谱 is found or bought).

* 补给, 资源, 素材 -- every other bag item's page (类型, 描述, 获取途径...), for the
  main app's item detail panel (D45).

Output: data/catalogue/recipes.json  {"items": [...], "recipes": [...], "details": [...]}.
Incremental: entries already in the file are kept and not re-requested, so a
re-run only fetches what the wiki added since. `--refresh` re-fetches all.

Scope and handling: as tools/fetch_catalogue.py -- Kuro's content, local use,
under the gitignored data/, one-time setup, serialised requests with a delay.

Run:  uv run python tools/fetch_recipes.py [--refresh]
"""

from __future__ import annotations

import argparse
import http.client
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

import fetch_pool

API = "https://api.kurobbs.com/wiki/core/catalogue/item/"
OUT = Path("data/catalogue/recipes.json")
CRAFTABLE, BLUEPRINTS = 1264, 1265
#: Bag categories whose item pages give the detail panel its description/source.
BAG = (1217, 1161, 1218)
DELAY_SECONDS = 0.3
TIMEOUT = 30
UA = "wuwa-vision/0.1 (local inventory scanner; personal use)"
WIKI_TYPE = "9"
#: One ingredient in a cell's text: "米*2", "云凝乳香 ×2".
_INGREDIENT = re.compile(r"([^*×xX\s][^*×]*?)\s*[*×]\s*(\d+)")
#: Pages name the same field differently; all mean "where it comes from".
_ALIASES = {"获取方式": "获取途径", "获得方式": "获取途径"}


def _post(endpoint: str, fields: dict, attempts: int = 3) -> dict:
    request = urllib.request.Request(
        API + endpoint, data=urllib.parse.urlencode(fields).encode(),
        headers={"User-Agent": UA, "wiki_type": WIKI_TYPE,
                 "Content-Type": "application/x-www-form-urlencoded"},
    )
    for attempt in range(1, attempts + 1):
        try:  # large pages now and then arrive cut short (IncompleteRead): ask again
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                payload = json.loads(response.read())
            break
        except (http.client.IncompleteRead, urllib.error.URLError, TimeoutError):
            if attempt == attempts:
                raise
            time.sleep(2 * attempt)
    if payload.get("code") != 200:
        raise RuntimeError(f"{endpoint}: {payload.get('msg')}")
    return payload["data"]


class _InfoTable(HTMLParser):
    """The 基础信息 table as rows of cells: [(cell text, [link texts])].

    Cell-based, whatever the tag: some pages mark labels with <th>, others with
    <td><strong>; some wrap an ingredient's name in a link, some put the icon and
    the name in one link. Only the row shape is common to all of them.
    """

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[tuple[str, list[str]]]] = []
        self._row: list[tuple[str, list[str]]] | None = None
        self._cell: list[str] | None = None
        self._links: list[str] = []
        self._link: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "tr":
            self._row = []
        elif tag in ("th", "td") and self._row is not None:
            self._cell, self._links = [], []
        elif tag == "a" and self._cell is not None:
            self._link = []
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._link is not None:
            self._links.append("".join(self._link).strip())
            self._link = None
        elif tag in ("th", "td") and self._cell is not None and self._row is not None:
            text = re.sub(r"\s+", " ", "".join(self._cell)).strip()
            self._row.append((text, [link for link in self._links if link]))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)
        if self._link is not None:
            self._link.append(data)


def parse_entry(html: str) -> dict:
    """The 基础信息 fields of one entry page, ingredients as (name, amount)."""
    table = _InfoTable()
    table.feed(html)
    out: dict = {}
    for cells in table.rows:
        if len(cells) < 2 or not cells[0][0]:
            continue  # the picture row spans the whole table
        label = _ALIASES.get(cells[0][0], cells[0][0])
        values = cells[1:]
        text = " ".join(t for t, _ in values if t)
        if label == "所需材料":
            out[label] = [
                {"name": m.group(1).strip(), "amount": int(m.group(2))}
                for cell_text, _ in values
                for m in _INGREDIENT.finditer(cell_text)
            ]
        elif label in ("食谱解锁", "配方解锁"):
            links = [link for _, cell_links in values for link in cell_links]
            out[label] = links[0] if links else text
        elif text:
            out.setdefault(label, text)
    return out


#: An entry linked by its address instead of its id: ".../mc/item/1347030627042816000".
_LINKED = re.compile(r"/item/(\d{6,})")


def entry_id_of(record: dict) -> str | None:
    """The wiki entry a catalogue tile leads to.

    Most tiles carry it as `content.linkConfig.entryId`. A few were set up by
    hand with a plain link (`content.linkUrl`) and no id -- 不灭航路 and 悲喜剧
    in the weapon catalogue -- and were skipped on every update for it, so the
    app had their icon and nothing else (D110).
    """
    content = record.get("content") or {}
    entry = (content.get("linkConfig") or {}).get("entryId") or record.get("entryId")
    if entry:
        return str(entry)
    linked = _LINKED.search(str(content.get("linkUrl") or ""))
    return linked.group(1) if linked else None


def _entries(catalogue_id: int) -> list[tuple[str, str]]:
    records = _post("getPage", {"catalogueId": catalogue_id, "page": 1, "limit": 1000})
    out = []
    for record in records["results"]["records"]:
        entry = entry_id_of(record)
        if record.get("name") and entry:
            out.append((record["name"].strip(), entry))
    return out


def _detail(entry_id: str) -> dict:
    data = _post("getEntryDetail", {"id": entry_id})
    for module in (data.get("content") or {}).get("modules") or []:
        if module.get("title") == "基础信息":
            html = "".join(c.get("content") or "" for c in module.get("components") or [])
            return parse_entry(html)
    return {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="re-fetch every entry")
    args = parser.parse_args()

    known = {"items": {}, "recipes": {}, "details": {}}
    if OUT.exists() and not args.refresh:
        saved = json.loads(OUT.read_text(encoding="utf-8"))
        for kind in known:
            known[kind] = {e["entry_id"]: e for e in saved.get(kind, [])}

    fetched = failed = 0
    sources = [("items", CRAFTABLE), ("recipes", BLUEPRINTS)]
    sources += [("details", c) for c in BAG]
    for kind, catalogue_id in sources:
        entries = _entries(catalogue_id)
        time.sleep(DELAY_SECONDS)
        # A bag item that is also craftable already has its page under "items".
        crafted = set(known["items"]) if kind == "details" else set()
        todo = [(n, e) for n, e in entries if e not in known[kind] and e not in crafted]
        print(f"{kind}: {len(entries)} on the wiki, {len(todo)} to fetch")
        # a few at a time (D202); one bad page does not stop the rest. Kept in the wiki's
        # order, as before, whatever order the answers came in.
        got: dict[str, dict] = {}
        for (name, entry_id), fields, error in fetch_pool.each(
                todo, lambda job: _detail(job[1]), pause=DELAY_SECONDS):
            if error is None:
                got[entry_id] = {"name": name, "entry_id": entry_id, **fields}
                fetched += 1
            else:
                print(f"  FAILED {name}: {error}", flush=True)
                failed += 1
        for _name, entry_id in todo:
            if entry_id in got:
                known[kind][entry_id] = got[entry_id]

    for entry in known["items"].values():
        # Some pages have no 类型 row; what unlocks the item says what it is.
        if "类型" not in entry:
            if "食谱解锁" in entry:
                entry["类型"] = "菜肴"
            elif "配方解锁" in entry:
                entry["类型"] = "药品"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(
        {kind: sorted(v.values(), key=lambda e: e["name"]) for kind, v in known.items()},
        ensure_ascii=False, indent=1,
    ), encoding="utf-8")
    print(f"fetched={fetched} failed={failed} -> {OUT}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
