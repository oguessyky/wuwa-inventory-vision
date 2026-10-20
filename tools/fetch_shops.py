# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Download what every shop sells: how many, and for how much (D158).

Source: the game's own data tables as datamined in the public GitHub repository
Arikatsu/WutheringWaves_Data, the one `fetch_levels.py` reads. The Kuro wiki says
which shops sell an item ("马和杂货购买 库默尼商行购买") and nothing more -- no
quantity, no price -- so the numbers are the game's, and the wiki is what they
are checked against.

* BinData/shop/shopfixed.json -- one row per thing a shop sells: `ShopId`,
  `ItemId`, `ItemNum` (what one purchase gives), `LimitNum` (how many purchases
  the shop allows; -1 = no limit), `Price` (the currency's item id and how much),
  and three condition ids (a good that has to be unlocked).
* BinData/shop/shopinfo.json -- each shop's name, as a text key.
* Textmaps/zh-Hans/multi_text/MultiText.json -- the texts behind the keys
  (`ItemInfo_<id>_Name`, `ShopInfo_<id>_ShopName`). 49 MB, read once and dropped:
  only the names asked for are kept.

Kept: goods whose item the catalogue has (`index.json`) -- a weapon or a 食谱 a
shop sells is not a bag item this app counts.

The wiki's shop names are matched to the game's shops by name where the two
agree, and otherwise by what is sold: 药剂商店 on the wiki is the game's 拾方药房
(every item the wiki lists under it is sold there, and nowhere else to speak
of). A shop the game's texts do not name at all is given the wiki's name the
same way: 共鸣医疗科. Where the goods prove nothing, nothing is claimed.

**When a limit resets is not in these tables.** The wiki says it for the few
shops it has a page for (its NPC商店 catalogue, 1634: five shops, the newest):
each page is a table of what the shop sells with 单价, 限购 and 刷新频率, the
shop's place, the NPC who keeps it, and a picture. Those shops are among the
ones the game's texts leave unnamed, so the pages name them too; their numbers
are checked against the game's and what differs is listed; and a good's
`refresh` is the wiki's word where it has one. Everywhere else the file has
the limit and no period (PLAN.md D158, D160).

A shop's `kind` (grocer, pharmacy, forge, diner, exchange, general) is read off
what it sells and how it is paid, for the app's own drawing of a shop: only
the five with a wiki page have a picture (data/catalogue/shops/, Kuro Games'
art, local display only, as every other picture the tools fetch).

The two sources are compared and what differs is listed, here and in the file
(`differs`): a shop the wiki names for an item that the game's table does not
have selling it, and the other way round. The game's table is what the app shows.

Output: data/catalogue/shops.json. Run it after fetch_recipes.py (it reads the
wiki's pages from recipes.json) and again after a game patch, or from the main
app's 更新 page.

Run:  uv run python tools/fetch_shops.py [--branch 3.7]
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

REPO = "Arikatsu/WutheringWaves_Data"
RAW = "https://raw.githubusercontent.com/{repo}/{branch}/{path}"
API = "https://api.github.com/repos/{repo}"
CATALOGUE = Path("data/catalogue")
OUT = CATALOGUE / "shops.json"
PICTURES = CATALOGUE / "shops"
#: The wiki's catalogue of shops that have a page of their own.
WIKI_SHOPS = 1634
PICTURE_WIDTH = 160
UA = "wuwa-vision/0.1 (local inventory scanner; personal use)"

#: "马和杂货购买", "海市兑换", "银盔杂货铺购买获得", "锻造商店购买（印造台旁）": a
#: source that is a shop. A sentence that merely has 购买 in it does not end so.
_SOLD = re.compile(r"^(.+?)(?:购买获得|购买|兑换)(?:[（(].*)?$")
_TAG = re.compile(r"</?\w+>")
_MARKS = str.maketrans("", "", "「」『』“”\"'·・ 　")
#: A wiki name is taken for a shop by its goods when the shop sells at least
#: `MIN_PROOF` of the items the wiki lists under it, and either it is the only shop
#: that sells `PROOF_SHARE` of them (面粉 and 糖 are sold everywhere: what tells one
#: grocer from the next is having the whole list), or it sells at least
#: `LOOSE_SHARE` of them and no other shop sells half as many.
MIN_PROOF = 3
PROOF_SHARE = 0.8
LOOSE_SHARE = 0.5


#: 刷新频率 as the wiki writes it -> what the file says.
REFRESH = {"每周刷新": "每周", "每日刷新": "每日", "每月刷新": "每月", "不刷新": "不刷新",
           "唯一": "唯一"}
_GOOD = re.compile(r"^(.+?)\s*[x×]\s*(\d+)$")
NAME_COLUMNS = ("道具名称", "物资名称")
#: A country the game's area table numbers but its texts do not name: the areas under it
#: are 黑海岸's islands (黑海岸群岛), so it is read as 黑海岸 (D161).
COUNTRY_UNNAMED = {900: "黑海岸"}
_NPC = re.compile(r"商店NPC[:：]\s*([^（(【]+)")
_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
_CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)


def _text(cell: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", cell)).split())


def parse_page(name: str, place: str | None, picture: str | None, page: str) -> dict:
    """One of the wiki's shop pages: where it is, who keeps it, and its table --
    per good the item, how many a purchase gives, 单价, 代币, 限购, 刷新频率."""
    rows = [[_text(c) for c in _CELL.findall(row)] for row in _ROW.findall(page)]
    # the column with the goods' names: 道具名称 on four pages, 物资名称 on 深空文献中心's (D161)
    head = next((r for r in rows if "单价" in r and any(c in r for c in NAME_COLUMNS)), None)
    npc = _NPC.search(" ".join(rows[0])) if rows else None
    goods = []
    for row in rows if head else []:
        if row is head or len(row) != len(head):
            continue
        cell = dict(zip(head, row, strict=True))
        good = _GOOD.match(next(cell[c] for c in NAME_COLUMNS if c in cell))
        if not good or not cell["单价"].isdigit():
            continue
        goods.append({
            "item": good.group(1).strip(), "amount": int(good.group(2)),
            "price": int(cell["单价"]), "currency": cell.get("代币") or None,
            "limit": int(cell["限购"]) if cell.get("限购", "").isdigit() else None,
            "refresh": REFRESH.get(cell.get("刷新频率", "")),
        })
    return {"name": name, "place": place or None, "npc": npc.group(1).strip() if npc else None,
            "picture": picture or None, "goods": goods}


def wiki_pages() -> list[dict]:
    """Every shop the wiki has a page for."""
    from fetch_recipes import _post, entry_id_of

    pages = []
    for record in _post("getPage", {"catalogueId": WIKI_SHOPS, "page": 1,
                                    "limit": 1000})["results"]["records"]:
        entry, content = entry_id_of(record), record.get("content") or {}
        if not entry or not record.get("name"):
            continue
        detail = _post("getEntryDetail", {"id": entry})
        page = "".join(c.get("content") or ""
                       for m in (detail.get("content") or {}).get("modules") or []
                       for c in m.get("components") or [])
        pages.append(parse_page(record["name"].strip(), content.get("subTitle"),
                                content.get("contentUrl"), page))
        time.sleep(0.3)
    return pages


def from_pages(shops: list[dict], pages: list[dict], links: dict[str, list[int]]) -> list[list]:
    """Put what the wiki's pages say on the shops they are (`links`): the place, the
    keeper, the picture's address, and per good when its limit starts over. Returns
    where the two disagree on a number, as [shop, item, what, game's, wiki's]."""
    by_id = {s["id"]: s for s in shops}
    differs = []
    for page in pages:
        ids = links.get(page["name"]) or []
        if len(ids) != 1:
            continue
        shop = by_id[ids[0]]
        shop.update(place=page["place"], npc=page["npc"], picture=page["picture"])
        said = {g["item"]: g for g in page["goods"]}
        for good in shop["goods"]:
            wiki = said.get(good["item"])
            if wiki is None:
                continue
            good["refresh"] = wiki["refresh"]
            price = good["price"][0]["amount"] if len(good["price"]) == 1 else None
            for what, game, theirs in (("price", price, wiki["price"]),
                                       ("limit", good["limit"], wiki["limit"]),
                                       ("amount", good["amount"], wiki["amount"])):
                if game != theirs and not (what == "limit" and theirs is None):
                    differs.append([label(shop), good["item"], what, game, theirs])
    return differs


#: A word in a shop's name that says what it is, whatever else it has on the shelf:
#: every pharmacy also sells salt.
_NAMED = (("pharmacy", ("药", "医", "诊")), ("diner", ("饭", "餐", "酒馆", "排档", "烘焙")))
_SORT = {"食材": "grocer", "加工品": "grocer", "菜肴": "diner", "药品": "diner",
         "药材": "pharmacy", "突破材料": "pharmacy", "共鸣者突破材料": "pharmacy",
         "武器与技能素材": "forge", "印造材料": "forge"}


def regions(marks: list[dict], fog: list[dict], areas: list[dict],
            text: dict[str, str]) -> dict[str, list[dict]]:
    """Where each place the game marks on its map is (D161): mark title -> the
    {country, town} of every mark with that title. A mark's fog block is in an
    area (`mapfog.json`); the area's parents end in a country (`area.json`).
    A mark in no block -- an event's stall -- is in no region."""
    in_area = {f["Fog"]: f["AreaId"] for f in fog}
    by_id = {a["AreaId"]: a for a in areas}
    out: dict[str, list[dict]] = defaultdict(list)
    for mark in marks:
        title = plain(text.get(mark.get("MarkTitle") or "", ""))
        area = by_id.get(in_area.get(mark.get("FogHide"), 0))
        if not title or area is None:
            continue
        town = plain(text.get(area.get("Title") or "", "")) or None
        country = (text.get(f"Country_{area['CountryId']}_Title")
                   or COUNTRY_UNNAMED.get(area["CountryId"]))
        place = {"country": country, "town": town}
        if place not in out[title]:
            out[title].append(place)
    return dict(out)


def place_shops(shops: list[dict], places: dict[str, list[dict]]) -> None:
    """Give each shop the places of the map marks that carry its name, or a name the
    wiki has for it. Two shops of one name (there are two “纪念品”商店) both get every
    place that name is marked at: which mark is which is not in the data."""
    marked = {_bare(title): where for title, where in places.items()}
    for shop in shops:
        names = [n for n in [shop["name"], *shop.get("also", [])] if n]
        found: list[dict] = []
        for name in names:
            for where in marked.get(_bare(name), []):
                if where not in found:
                    found.append(where)
        shop["regions"] = found


def kind_of(shop: dict, types: dict[str, str]) -> str:
    """What sort of shop this is, for the drawing the app gives it: from how it
    is paid, then its name, then what most of its goods are (`types`: item ->
    the wiki's 类型, a dish or potion being 菜肴 / 药品)."""
    currencies = {p["item"] for g in shop["goods"] for p in g["price"]}
    if currencies and currencies != {"贝币"}:
        return "exchange"
    for kind, words in _NAMED:
        if any(word in (shop["name"] or "") for word in words):
            return kind
    counts: dict[str, int] = defaultdict(int)
    for good in shop["goods"]:
        counts[_SORT.get(types.get(good["item"], ""), "general")] += 1
    return max(counts.items(), key=lambda kv: (kv[1], kv[0]), default=("general", 0))[0]


def _get(url: str) -> object:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read())


def plain(name: str) -> str:
    """A name as the game shows it: 戏服与面具行<word>「梦中人」</word> without its tags."""
    return _TAG.sub("", name).strip()


def _bare(name: str) -> str:
    return name.translate(_MARKS)


def link(shops: list[dict], wiki: dict[str, set[str]]) -> dict[str, list[int]]:
    """Which of the game's shops each wiki name means: name -> shop ids.

    By name when they are the same name (two shops can share one: there are two
    “纪念品”商店). Otherwise by goods, when the goods prove it. Otherwise by a
    name inside the other (心之集域·夜之城的人工智能杂货铺 is 人工智能杂货铺), and
    failing that by nothing: the wiki also names shops that are not shops in
    this table at all (演练商店, 深塔兑换所).
    """
    out: dict[str, list[int]] = {}
    for name, items in wiki.items():
        exact = [s["id"] for s in shops if s["name"] and _bare(s["name"]) == _bare(name)]
        if exact:
            out[name] = exact
            continue
        ranked = sorted(((len(items & {g["item"] for g in s["goods"]}), s["id"]) for s in shops),
                        reverse=True)
        best, runner_up = ranked[0] if ranked else (0, 0), ranked[1] if len(ranked) > 1 else (0, 0)
        whole = best[0] >= PROOF_SHARE * len(items) > runner_up[0]
        apart = best[0] >= LOOSE_SHARE * len(items) and 2 * runner_up[0] <= best[0]
        if best[0] >= MIN_PROOF and (whole or apart):
            out[name] = [best[1]]
            continue
        out[name] = [s["id"] for s in shops if s["name"] and _bare(name) and _bare(s["name"])
                     and (_bare(name) in _bare(s["name"]) or _bare(s["name"]) in _bare(name))]
    return out


def wiki_shops(details: list[dict]) -> dict[str, set[str]]:
    """The wiki's word: shop -> the items whose 获取途径 names it."""
    out: dict[str, set[str]] = defaultdict(set)
    for page in details:
        for part in str(page.get("获取途径") or "").split():
            sold = _SOLD.match(part)
            if sold and page.get("name"):
                out[sold.group(1)].add(page["name"])
    return dict(out)


def build(fixed: list[dict], info: list[dict], text: dict[str, str],
          known: set[str]) -> list[dict]:
    """The game's word: every shop with the goods the catalogue has, in the
    shop's own order. A shop with none of them is left out."""
    names = {s["Id"]: plain(text.get(s.get("ShopName") or "", "")) for s in info}
    goods: dict[int, list[dict]] = defaultdict(list)
    for row in sorted(fixed, key=lambda r: (r["ShopId"], r.get("SortIndex", 0), r["Id"])):
        item = text.get(f"ItemInfo_{row['ItemId']}_Name")
        if not row.get("Show", True) or item not in known:
            continue
        price = [{"item": text.get(f"ItemInfo_{p['Key']}_Name") or f"#{p['Key']}",
                  "amount": p["Value"]} for p in row.get("Price") or []]
        goods[row["ShopId"]].append({
            "item": item, "amount": row.get("ItemNum") or 1,
            "limit": row["LimitNum"] if row.get("LimitNum", -1) >= 0 else None,
            "price": price,
            # a good that has to be unlocked first, or that goes away: said, not explained
            "gated": any(row.get(k) for k in ("CondId", "VisableCondition", "DisableCondition")),
        })
    return [{"id": shop, "name": names.get(shop) or None,
             "named_by": "game" if names.get(shop) else None, "goods": rows}
            for shop, rows in sorted(goods.items())]


def name_from_wiki(shops: list[dict], links: dict[str, list[int]]) -> None:
    """What the wiki calls a shop, where that is not what the game calls it: the
    name of a shop the game left unnamed (`named_by` "wiki"), and another name
    for one it did name (`also`)."""
    by_id = {s["id"]: s for s in shops}
    for name, ids in sorted(links.items()):
        if len(ids) != 1:
            continue
        shop = by_id[ids[0]]
        if not shop["name"]:
            shop["name"], shop["named_by"] = name, "wiki"
        elif _bare(shop["name"]) != _bare(name):
            shop.setdefault("also", []).append(name)


def label(shop: dict) -> str:
    return shop["name"] or f"#{shop['id']}"


def compare(shops: list[dict], wiki: dict[str, set[str]],
            links: dict[str, list[int]]) -> dict[str, list[list[str]]]:
    """Where the two disagree on who sells what, as [shop, item] pairs."""
    by_id = {s["id"]: s for s in shops}
    wiki_only = []
    said: dict[int, set[str]] = defaultdict(set)
    for name, items in sorted(wiki.items()):
        sold = {g["item"] for shop in links.get(name, []) for g in by_id[shop]["goods"]}
        wiki_only += [[name, item] for item in sorted(items - sold)]
        for shop in links.get(name, []):
            said[shop] |= items
    data_only = [[label(shop), item] for shop in shops
                 for item in sorted({g["item"] for g in shop["goods"]} - said[shop["id"]])]
    return {"wiki_only": wiki_only, "data_only": data_only}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch", help="game version branch (default: the repo's default)")
    args = parser.parse_args()
    # what is printed is Chinese names; a console in another code page must not stop the fetch
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    branch = args.branch or _get(API.format(repo=REPO))["default_branch"]  # type: ignore[index]

    def data(path: str) -> list[dict]:
        return _get(RAW.format(repo=REPO, branch=branch, path=path))  # type: ignore[return-value]

    index = json.loads((CATALOGUE / "index.json").read_text(encoding="utf-8"))
    recipes = CATALOGUE / "recipes.json"
    details = (json.loads(recipes.read_text(encoding="utf-8")).get("details") or []
               if recipes.exists() else [])
    fixed, info = data("BinData/shop/shopfixed.json"), data("BinData/shop/shopinfo.json")
    # where a shop is: its map mark, the mark's fog block, the block's area (D161)
    marks = [m for m in data("BinData/map_mark/mapmark.json") if m.get("MarkTitle")]
    fog, areas = data("BinData/mapfog/mapfog.json"), data("BinData/area/area.json")
    wanted = ({f"ItemInfo_{r['ItemId']}_Name" for r in fixed}
              | {f"ItemInfo_{p['Key']}_Name" for r in fixed for p in r.get("Price") or []}
              | {s["ShopName"] for s in info if s.get("ShopName")}
              | {m["MarkTitle"] for m in marks} | {a["Title"] for a in areas if a.get("Title")}
              | {f"Country_{a['CountryId']}_Title" for a in areas})
    print("reading the game's texts (49 MB, once) ...", flush=True)
    text = {r["Id"]: r["Content"]
            for r in data("Textmaps/zh-Hans/multi_text/MultiText.json") if r["Id"] in wanted}

    wiki = wiki_shops(details)
    pages = wiki_pages()
    known = {e["name"] for e in index}
    for page in pages:      # a page is the wiki's word on its shop, fuller than any 获取途径
        # (a 食谱 a shop sells is not a bag item: it is on neither side of the comparison)
        wiki[page["name"]] = wiki.get(page["name"], set()) | {
            g["item"] for g in page["goods"] if g["item"] in known}
    shops = build(fixed, info, text, known)
    links = link(shops, wiki)
    name_from_wiki(shops, links)
    differs = compare(shops, wiki, links)
    differs["numbers"] = from_pages(shops, pages, links)
    place_shops(shops, regions(marks, fog, areas, text))
    types = {d["name"]: (d.get("类型") or "").strip() for d in details if d.get("name")}
    made = (json.loads(recipes.read_text(encoding="utf-8")).get("items") or []
            if recipes.exists() else [])
    types.update({d["name"]: d.get("类型") or "菜肴" for d in made if d.get("name")})
    PICTURES.mkdir(parents=True, exist_ok=True)
    from fetch_builds import _download

    for shop in shops:
        shop["kind"] = kind_of(shop, types)
        # the picture's address is the wiki's; what is kept is the file fetched from it
        shop["icon"] = _download(shop.pop("picture", None), PICTURES / f"{shop['id']}.webp",
                                 PICTURE_WIDTH)
    OUT.write_text(json.dumps({
        "source": f"github.com/{REPO} ({branch}) BinData/shop",
        "shops": shops, "differs": differs,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    goods = sum(len(s["goods"]) for s in shops)
    unplaced = [s["name"] or f"#{s['id']}" for s in shops if not s["regions"]]
    print(f"  placed on the map: {len(shops) - len(unplaced)} shops; not: {', '.join(unplaced)}")
    nameless = [s["id"] for s in shops if not s["name"]]
    print(f"{branch}: {len(shops)} shops, {goods} goods the catalogue has -> {OUT}")
    by_wiki = [s["name"] for s in shops if s["named_by"] == "wiki"]
    if by_wiki:
        print(f"  named from the wiki by their goods: {', '.join(by_wiki)}")
    for shop in shops:
        if shop.get("also"):
            print(f"  {shop['name']} is what the wiki calls {' / '.join(shop['also'])}")
    if nameless:
        print(f"  not named by the game or the wiki: {', '.join(map(str, nameless))}")
    weekly = sum(1 for s in shops for g in s["goods"] if g.get("refresh") == "每周")
    print(f"  {len(pages)} shops have a wiki page of their own: "
          f"{', '.join(p['name'] for p in pages)}; {weekly} goods are said to start over weekly")
    for shop, item, what, game, theirs in differs["numbers"]:
        print(f"  {shop} / {item}: {what} is {game} in the game's table, {theirs} on the wiki")
    for key, label in (("wiki_only", "the wiki names a shop the game's table does not have "
                                     "selling it"),
                       ("data_only", "the game's table has a shop selling it that the wiki "
                                     "does not name")):
        pairs = differs[key]
        print(f"  {len(pairs)} where {label}"
              + (": " + ", ".join(f"{shop} / {item}" for shop, item in pairs[:6])
                 + (" ..." if len(pairs) > 6 else "") if pairs else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
