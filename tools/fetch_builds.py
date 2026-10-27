# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Download every resonator and weapon: build costs, profile and art (D45, D46).

Source: Kuro's wiki (wiki.kurobbs.com), the same API as tools/fetch_catalogue.py.

* 共鸣者 (resonators): the 角色突破材料 tabs (six ascensions) and the 技能突破材料
  tabs (each skill's LV.2-10 and its extra nodes) -- summed, one full build, and
  kept step by step for the planner (6 ascensions; per skill, LV.2..10 and each
  分支强化 node); the
  profile (属性, 武器, 性别, 出生, 特殊料理, 实装版本), the 武器推荐 ranking (its
  first pick is usually the 专武); and two images, resized by
  the wiki's CDN: the list card and the full 立绘 portrait.
* 武器 (weapons): the 突破材料总览 block (the wiki's own total of all ascensions)
  or, on pages without one, the per-level 突破材料 block summed (the per-level
  block is also kept, as six ascensions, for the planner); plus rarity,
  weapon type, version and 获取途径 (limited 活动唤取 or standard 常驻). Weapon
  icons come with the catalogue (fetch_catalogue.py).

The materials page's stock targets come from these totals (D45 decision 9), and
so do the material families that combine upward: each build uses exactly one
enemy-drop family and one weapon-type family, tier after tier.

Output: data/catalogue/builds.json {"resonators": {...}, "weapons": {...}} and
data/catalogue/resonators/<entry id>.card.webp / .webp.
Incremental: complete entries are not re-requested; `--refresh` re-fetches all.
Scope and handling as tools/fetch_catalogue.py: Kuro's content, local use,
gitignored data/, run by hand (or from the main app's 更新 page), serialised
requests with a delay.

Run:  uv run python tools/fetch_builds.py [--refresh]
"""

from __future__ import annotations

import argparse
import json
import re
import threading
import time
import urllib.request
from html import unescape
from pathlib import Path

import fetch_pool
from fetch_recipes import UA, _entries, _InfoTable, _post

OUT = Path("data/catalogue/builds.json")
ART = OUT.parent / "resonators"
RESONATORS, WEAPONS = 1105, 1106
DELAY_SECONDS = 0.3
#: The CDN resizes and re-encodes on request: 583 KB PNG -> ~100 KB WebP.
PORTRAIT_WIDTH, CARD_WIDTH = 900, 360
#: "低频啸叫声核 x4", "海蚀嵌合体210 * 6", "贝币 ×5000".
_PAIR = re.compile(r"([^\s|:：*×]+?)\s*[*×xX]\s*(\d+)")
#: The same with the sign left out, as the wiki now and then writes it: "游霞惊梦 12",
#: "改造镣环3" (D149). Read as an amount only after a name the catalogue has.
_BARE = re.compile(r"([^\s|:：*×\d]+)\s*(\d+)(?![\d.])")
#: The names an amount with no sign may follow: the catalogue's items, and 贝币.
_NAMES: frozenset[str] = frozenset()


def learn_names(index: Path = Path("data/catalogue/index.json")) -> int:
    """Read the item names `materials` may trust. Without them it reads as strictly as before."""
    global _NAMES  # noqa: PLW0603 -- one table, read once before the pages are
    try:
        entries = json.loads(index.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        entries = []
    names = {e["name"] for e in entries if isinstance(e, dict) and e.get("name")}
    _NAMES = frozenset(names | {"贝币"})
    return len(_NAMES)
#: A linked name is the true one; the wiki sometimes leaves a stray character
#: between the link and its amount ("<a>碑趺古钟</a>钟x1").
_STRAY = re.compile(r"</a>[^<\sx×*\d]{1,3}(?=\s*[*×xX]\s*\d)")
#: role-component info lines ("属性：衍射") -> builds.json keys.
_PROFILE = {"属性": "element", "武器": "weapon", "性别": "gender", "出生": "birthplace"}
#: 其他信息 rows -> builds.json keys.
_OTHER = {"特殊料理": "dish", "实装版本": "version", "所属": "faction"}


def _text(html: str) -> str:
    html = _STRAY.sub("</a>", unescape(html or "")).replace("</tr>", " | ")
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def materials(text: str) -> dict[str, int]:
    """Sum every "name x N" in `text`. Names must hold Chinese (skips "LV.2 x")."""
    out: dict[str, int] = {}
    for name, amount in _PAIR.findall(text):
        name = name.strip()
        if any("一" <= ch <= "鿿" for ch in name):
            out[name] = out.get(name, 0) + int(amount)
    # What is left may hold a material whose sign the wiki dropped. A number after
    # any other words ("所需等级 60", "等级上限 70") is not an amount of anything.
    if _NAMES:
        for name, amount in _BARE.findall(_PAIR.sub(" ", text)):
            if name in _NAMES:
                out[name] = out.get(name, 0) + int(amount)
    return out


def _components(data: dict):  # noqa: ANN202 -- yields wiki page components
    for module in (data.get("content") or {}).get("modules") or []:
        yield from module.get("components") or []


def _download(url: str | None, dest: Path, width: int) -> str | None:
    """Save `url` resized to `width` as WebP; the file name, or None without a url."""
    if not url:
        return None
    if dest.exists() and dest.stat().st_size:
        return dest.name  # art does not change between runs: fetched once
    sized = f"{url}?x-oss-process=image/resize,w_{width}/format,webp"
    dest.write_bytes(_fetch(sized))
    return dest.name


def _fetch(url: str, attempts: int = 3, deadline: float = 30.0) -> bytes:
    """GET with a hard deadline per attempt. The CDN now and then stalls before the
    socket timeout applies (name lookup / connect), so the wait runs in a daemon
    thread that is abandoned when it overruns."""
    for attempt in range(1, attempts + 1):
        box: dict = {}

        def get(box: dict = box) -> None:
            try:
                request = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(request, timeout=deadline) as response:
                    box["data"] = response.read()
            except Exception as exc:  # noqa: BLE001 -- reported below
                box["error"] = exc

        worker = threading.Thread(target=get, daemon=True)
        worker.start()
        worker.join(deadline)
        if "data" in box:
            return box["data"]
        if attempt == attempts:
            raise box.get("error") or TimeoutError(f"no answer in {deadline:.0f}s: {url}")
        time.sleep(2 * attempt)
    raise AssertionError("unreachable")


def other_info(text: str) -> dict[str, str]:
    """The 其他信息 table: "身份 今州令尹 | 所属 今州 | 特殊料理 迎春酥 | ..."."""
    out: dict[str, str] = {}
    for cell in text.split("|"):
        label, _, value = cell.strip().partition(" ")
        if label in _OTHER and value.strip():
            out[_OTHER[label]] = value.strip()
    return out


def _rows(html: str) -> list[list[str]]:
    table = _InfoTable()
    table.feed(_STRAY.sub("</a>", unescape(html or "")))
    return [[text for text, _ in row] for row in table.rows]


def skill_costs(html: str) -> dict:
    """One 技能突破材料 tab: {"levels": [LV.2 .. LV.10 costs], "nodes": [each 分支强化]}.

    The table has the node costs first (rows of two cells; each node pays 贝币
    once, so a second 贝币 starts the next node), then a "LV.2 .. LV.10" header
    row and one row with a cell per level.
    """
    rows = _rows(html)
    nodes: list[dict[str, int]] = []
    levels: list[dict[str, int]] = []
    header = next((i for i, r in enumerate(rows) if r and r[0].startswith("LV.")), None)
    for row in rows[:header if header is not None else len(rows)]:
        cost = materials(" ".join(row))
        if not cost:
            continue
        if not nodes or ("贝币" in cost and "贝币" in nodes[-1]):
            nodes.append({})
        for name, n in cost.items():
            nodes[-1][name] = nodes[-1].get(name, 0) + n
    if header is not None and header + 1 < len(rows):
        levels = [materials(cell) for cell in rows[header + 1]]
    return {"levels": levels, "nodes": nodes}


def weapon_steps(text: str) -> list[dict[str, int]]:
    """"20级 低频呓语声核 * 6 | 40级 ... | 80级 ..." -> the six ascensions' costs."""
    return [materials(seg) for seg in text.split("|") if re.match(r"\s*\d+级", seg)]


def recommended(text: str) -> list[str]:
    """The 武器推荐 ranking: "时和岁稔 ＞苍鳞千嶂 ＞浩境粼光 >纹秋 | 武器首位推荐 ..."."""
    head = text.split("|")[0].strip().removeprefix("武器推荐").strip()
    # "停驻之烟 /华彩乐段" is either of two: the first stands for the rank.
    return [w.split("/")[0].strip() for w in re.split(r"[＞>]", head) if w.strip()]


def resonator(entry_id: str, card_url: str | None = None) -> dict:
    total: dict[str, int] = {}
    out: dict = {"ascension": [], "skills": {}}
    portrait_url = None
    for comp in _components(_post("getEntryDetail", {"id": entry_id})):
        title = comp.get("title")
        if title in ("角色突破材料", "技能突破材料"):
            for tab in comp.get("tabs") or []:
                for name, n in materials(_text(tab.get("content"))).items():
                    total[name] = total.get(name, 0) + n
                if title == "角色突破材料":
                    out["ascension"].append(materials(_text(tab.get("content"))))
                else:
                    out["skills"][tab.get("title") or "?"] = skill_costs(tab.get("content"))
        elif title == "其他信息":
            out.update(other_info(_text(comp.get("content"))))
        elif title == "角色养成推荐":
            for tab in comp.get("tabs") or []:
                if tab.get("title") == "武器推荐":
                    out["recommended"] = recommended(_text(tab.get("content")))
        elif comp.get("type") == "role-component":
            role = comp.get("role") or {}
            for line in role.get("info") or []:
                label, _, value = (line.get("text") or "").partition("：")
                if label in _PROFILE and value:
                    out[_PROFILE[label]] = value.strip()
            figures = role.get("figures") or []
            portrait_url = next((f.get("url") for f in figures if f.get("name") == "立绘"),
                                figures[0].get("url") if figures else None)
            if role.get("roleDescription"):
                out["description"] = role["roleDescription"].strip()
            # the page's own second title is the name in English ("Hsin"): what a
            # pull export calls them, when there is no game id to go by (D133)
            out["english"] = (role.get("subtitle") or "").strip()
    ART.mkdir(parents=True, exist_ok=True)
    out["portrait"] = _download(portrait_url, ART / f"{entry_id}.webp", PORTRAIT_WIDTH)
    out["card"] = _download(card_url, ART / f"{entry_id}.card.webp", CARD_WIDTH)
    return {"materials": total, **out}


def weapon(entry_id: str) -> dict:
    out: dict = {"materials": {}}
    per_level: dict[str, int] = {}
    for comp in _components(_post("getEntryDetail", {"id": entry_id})):
        title = comp.get("title") or ""
        if title.startswith("突破材料总览"):
            out["materials"] = materials(_text(comp.get("content")))
        elif title == "突破材料" or title.startswith("突破材料详细"):
            out["ascension"] = weapon_steps(_text(comp.get("content")))
            if title == "突破材料":
                per_level = materials(_text(comp.get("content")))
        elif title == "基础信息":
            text = _text(comp.get("content"))
            kind = re.search(r"武器类型\s*\|?\s*([^\s|]+)", text)
            if kind:
                out["type"] = kind.group(1)
            version = re.search(r"实装版本\s*\|?\s*(V[\d.]+)", text)
            out["version"] = version.group(1) if version else None
        elif title == "武器描述":
            # "获取途径： 武器活动唤取" (limited) / "武器常驻唤取，..." (standard)
            source = re.search(r"获取途径[:：]?\s*([^|]+)", _text(comp.get("content")))
            out["source"] = source.group(1).strip() if source else None
    out["materials"] = out["materials"] or per_level
    return out


def complete(kind: str, entry: dict) -> bool:
    """Worth keeping as is: costs read, and for a resonator its profile and art. An
    unreleased resonator (no cost tables yet) is asked again on every run, so its
    costs arrive with the patch that releases it; its art is not downloaded twice."""
    if not entry.get("materials"):
        return False
    if kind == "weapons":
        return "version" in entry and "ascension" in entry
    # "english" arrived with D133: a page read before it is read once more for it
    return bool("element" in entry and entry.get("portrait") and "recommended" in entry
                and entry.get("ascension") and "english" in entry)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="re-fetch every entry")
    args = parser.parse_args()

    learn_names()
    known: dict = {"resonators": {}, "weapons": {}}
    if OUT.exists() and not args.refresh:
        known.update(json.loads(OUT.read_text(encoding="utf-8")))

    fetched = failed = 0
    for kind, catalogue_id in (("resonators", RESONATORS), ("weapons", WEAPONS)):
        records = _post("getPage", {"catalogueId": catalogue_id, "page": 1, "limit": 1000})
        listed = {r["name"].strip(): r.get("content") or {}
                  for r in records["results"]["records"] if r.get("name")}
        entries = _entries(catalogue_id)
        time.sleep(DELAY_SECONDS)
        todo = [(n, e) for n, e in entries if not complete(kind, known[kind].get(n) or {})]
        print(f"{kind}: {len(entries)} on the wiki, {len(todo)} to fetch", flush=True)
        def one(job: tuple[str, str], kind: str = kind, listed: dict = listed) -> dict:
            name, entry_id = job
            card = listed.get(name, {}).get("contentUrl")
            entry = resonator(entry_id, card) if kind == "resonators" else weapon(entry_id)
            star = str(listed.get(name, {}).get("star") or "")
            entry.update(entry_id=entry_id, rarity=int(star) if star.isdigit() else 0)
            return entry

        # a few at a time (D202); one bad page does not stop the rest. Kept in the wiki's
        # order, as before, whatever order the answers came in.
        got: dict[str, dict] = {}
        for (name, _entry_id), entry, error in fetch_pool.each(todo, one, pause=DELAY_SECONDS):
            if error is None:
                got[name] = entry
                fetched += 1
                print(f"  + {name}", flush=True)
            else:
                print(f"  FAILED {name}: {error}", flush=True)
                failed += 1
        for name, _entry_id in todo:
            if name in got:
                known[kind][name] = got[name]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(known, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"fetched={fetched} failed={failed} -> {OUT}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
