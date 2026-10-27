# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""What is known about every item, whether or not it was ever scanned (D42-D45).

Three sources, all optional:
* `data/catalogue/index.json` (tools/fetch_catalogue.py): name, rarity, bag tab,
  icon file. Without it, the shipped gallery pack supplies names, rarities, tabs.
* `data/catalogue/recipes.json` (tools/fetch_recipes.py): each item's page --
  类型, 描述, 获取途径; for dishes and potions also 所需材料 and the 食谱/配方
  that teaches them; and every 食谱/配方 with where it is found.
* `data/catalogue/builds.json` (tools/fetch_builds.py): every resonator and weapon,
  what a full build costs, a resonator's profile and art.

Over them, `overrides.json`: what the user added or fixed by hand on the 更新
page (D46) -- materials, material families, weapons the wiki lacks or gets wrong.

Headless: the main app's pages only render what this returns.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

CATALOGUE_DIR = Path("data/catalogue")
OVERRIDES = "overrides.json"
#: What overrides.json holds; every key optional.
EMPTY_OVERRIDES: dict = {"items": {}, "families": [], "weapons": {}, "resonators": {},
                         "signatures": {}, "gids": {}, "pull_english": {}, "english": {}}
#: Pulls named by hand and shipped with the app (D135): game id -> the name here
#: and the English name a pull export gives it. Written by tools/make_pull_names.py
#: from what a maintainer named on the 更新 page; nothing in it is fetched.
PULL_NAMES = Path(__file__).resolve().parents[2] / "assets" / "pull_names.json"
#: Rows of a build that Kuro's wiki has wrong, and what they should be (D149).
BUILD_FIXES = Path(__file__).resolve().parents[2] / "assets" / "build_fixes.json"
#: Ingredients of a dish that Kuro's wiki has wrong, and what the game asks for (D155).
RECIPE_FIXES = Path(__file__).resolve().parents[2] / "assets" / "recipe_fixes.json"
#: An item's rarity that Kuro's wiki has wrong, and what the game shows (D199).
ITEM_FIXES = Path(__file__).resolve().parents[2] / "assets" / "item_fixes.json"


def read_build_fixes(path: Path | None = None) -> dict[str, dict[str, list[dict]]]:
    """{"resonators": {name: [{"at", "was", "now"}]}, "weapons": {...}}; empty without the file."""
    path = Path(path or BUILD_FIXES)
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return {kind: {str(name): [f for f in fixes if isinstance(f, dict)]
                   for name, fixes in (data.get(kind) or {}).items() if isinstance(fixes, list)}
            for kind in ("resonators", "weapons")}


def apply_build_fixes(builds: dict, fixes: dict) -> int:
    """Put right the rows the wiki has wrong (D149). Returns how many were changed.

    A fix names one row -- `at`: ["ascension", 3] or ["skills", "共鸣回路", "nodes", 0] --
    with what the wiki says there (`was`) and what the game charges (`now`). It is
    applied only while the row still reads `was`: once Kuro corrects the page, or the
    reader learns to read it, the fix has nothing to do and does nothing, so a stale
    correction can never overwrite newer data. The build's total moves by the same
    amounts as the row.
    """
    changed = 0
    for kind, entries in fixes.items():
        for name, rows in entries.items():
            build = (builds.get(kind) or {}).get(name)
            if not build:
                continue
            for fix in rows:
                if not isinstance(fix, dict):
                    continue
                where, was, now = fix.get("at"), fix.get("was"), fix.get("now")
                if not (isinstance(where, list) and isinstance(was, dict)
                        and isinstance(now, dict)):
                    continue
                holder = build
                try:
                    for step in where[:-1]:
                        holder = holder[step]
                    if holder[where[-1]] != was:
                        continue
                except (KeyError, IndexError, TypeError):
                    continue
                holder[where[-1]] = dict(now)
                total = build.setdefault("materials", {})
                for item in set(was) | set(now):
                    total[item] = total.get(item, 0) + now.get(item, 0) - was.get(item, 0)
                    if total[item] <= 0:
                        del total[item]
                changed += 1
    return changed


def read_item_fixes(path: Path | None = None) -> dict[str, dict[str, int]]:
    """{name: {"was": wiki's rarity, "now": the game's}}; empty without the file (D199)."""
    path = Path(path or ITEM_FIXES)
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return {str(name): {"was": int(fix["was"]), "now": int(fix["now"])}
            for name, fix in (data.get("rarity") or {}).items()
            if isinstance(fix, dict) and {"was", "now"} <= set(fix)}


def _item_fixes_stamp() -> str:
    """Which item fixes are in force: a list worked out from rarities is redone when they change."""
    return str(ITEM_FIXES.stat().st_mtime_ns) if ITEM_FIXES.exists() else "-"


def fixed_rarity(name: str, rarity: int, fixes: dict[str, dict[str, int]] | None = None) -> int:
    """The game's rarity for `name`, where the wiki still says what was fixed (D199)."""
    fix = (read_item_fixes() if fixes is None else fixes).get(name)
    return fix["now"] if fix and rarity == fix["was"] else rarity


def read_recipe_fixes(path: Path | None = None) -> dict[str, list[dict]]:
    """{dish: [{"was", "now"}]}; empty without the file."""
    path = Path(path or RECIPE_FIXES)
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    wrong = data.get("ingredients")
    return {str(dish): [f for f in fixes if isinstance(f, dict)]
            for dish, fixes in (wrong if isinstance(wrong, dict) else {}).items()
            if isinstance(fixes, list)}


def apply_recipe_fixes(dishes: list[dict], fixes: dict[str, list[dict]]) -> int:
    """Put right the ingredients the wiki has wrong (D155). Returns how many were changed.

    A fix names a dish, what its page calls one ingredient (`was`) and what the game
    calls it (`now`), checked in the game by hand. As with a build's rows (D149) it is
    applied only while the page still says `was`: once Kuro corrects it the fix has
    nothing to do. The amount is the page's and is left alone.
    """
    changed = 0
    for dish in dishes:
        for fix in fixes.get(dish.get("name") or "", ()):
            was, now = fix.get("was"), fix.get("now")
            if not (isinstance(was, str) and isinstance(now, str) and was and now):
                continue
            for ingredient in dish.get("所需材料") or []:
                if ingredient.get("name") == was:
                    ingredient["name"] = now
                    changed += 1
    return changed


def plain_english(name: str) -> str:
    """An English name as letters only: "The Shorekeeper" and "Shorekeeper" are one."""
    letters = "".join(c for c in name.casefold() if c.isalnum())
    return letters[3:] if letters.startswith("the") and len(letters) > 6 else letters


def read_pull_names(path: Path | None = None) -> dict[str, dict[str, dict[str, str]]]:
    """{"weapons": {id: {"name", "english"}}, "resonators": {...}}; empty without the file."""
    path = Path(path or PULL_NAMES)
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return {kind: {str(gid): dict(entry) for gid, entry in (data.get(kind) or {}).items()
                   if isinstance(entry, dict) and entry.get("name")}
            for kind in ("weapons", "resonators")}
#: A resonator's own dish says which ordinary dish it comes from: "使用吟霖烹饪碎金饭
#: 有概率烹饪获得" (the wiki doubles the verb on some pages).
_COOKED_FROM = re.compile(r"使用.+?烹饪(?:烹饪)?(.+?)有概率")
#: What a page's 类型 says of something that is cooked or mixed (cooking.TYPES).
CRAFTED_TYPES = ("菜肴", "药品")


def read_game_english(path: Path | None = None) -> dict[str, str]:
    """{a weapon's name here: its English name in the game}, for the weapons nobody
    has yet pulled and named (D147). No id goes with these: a pull is placed by
    the name its export gives it, which is this name."""
    path = Path(path or PULL_NAMES)
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return {str(name): str(english) for name, english in (data.get("english") or {}).items()
            if name and english}


def read_overrides(directory: Path | None = None) -> dict:
    path = Path(directory or CATALOGUE_DIR) / OVERRIDES
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return {k: data.get(k, type(v)()) for k, v in EMPTY_OVERRIDES.items()}


def write_overrides(data: dict, directory: Path | None = None) -> None:
    path = Path(directory or CATALOGUE_DIR) / OVERRIDES
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = {k: data.get(k, type(v)()) for k, v in EMPTY_OVERRIDES.items()}
    path.write_text(json.dumps(clean, ensure_ascii=False, indent=1), encoding="utf-8")


#: The weapon-type icons. The app ships five drawings of its own (web/static/icons/)
#: and none of the game's (D140). Whoever would rather see other pictures -- the
#: game's own, say -- puts them, under the same names, in this machine's
#: avatars/ folder or in web/static/icons/game/, and those are shown instead.
GAME_ICONS = Path(__file__).resolve().parent / "web" / "static" / "icons" / "game"
WEAPON_TYPE_ICONS = {"长刃": "wp-broadblade.svg", "迅刀": "wp-sword.svg", "佩枪": "wp-pistols.svg",
                     "臂铠": "wp-gauntlets.svg", "音感仪": "wp-rectifier.svg"}


#: How often, at most, a catalogue folder is looked at again for files put there (D171).
LOOK = 5.0
_monotonic = time.monotonic


@dataclass
class Catalogue:
    directory: Path = CATALOGUE_DIR
    _index: dict[str, dict] = field(default_factory=dict, repr=False)

    @classmethod
    def load(cls, directory: Path | None = None) -> Catalogue:
        """Read the catalogue from `directory` (default: CATALOGUE_DIR, looked up now)."""
        catalogue = cls(Path(directory or CATALOGUE_DIR))
        index = catalogue.directory / "index.json"
        if index.exists():
            fixes = read_item_fixes()
            for entry in json.loads(index.read_text(encoding="utf-8")):
                if entry.get("rarity") is not None:
                    entry["rarity"] = fixed_rarity(entry["name"], int(entry["rarity"]), fixes)
                catalogue._index[entry["name"]] = entry
        else:
            from .recognize.pack import PACK_PATH, read_pack

            if PACK_PATH.exists():
                meta, _, _ = read_pack()
                for name, rarity, tab in zip(
                    meta["names"], meta["rarities"], meta["tabs"], strict=True
                ):
                    catalogue._index[name] = {"name": name, "rarity": rarity, "tab": tab}
        for name, item in catalogue.overrides["items"].items():
            base = catalogue._index.get(name, {"name": name})
            catalogue._index[name] = {**base, **{k: item[k] for k in ("rarity", "tab")
                                                 if k in item}}
        return catalogue

    @cached_property
    def overrides(self) -> dict:
        return read_overrides(self.directory)

    @cached_property
    def drawn_identically(self) -> frozenset[str]:
        """Items whose picture is another's, pixel for pixel, at the same rarity (D200): the
        four 溶剂, 撞金合剂 / 划音合剂, 醋 / 糖醋汁 ... Only the panel tells them apart, so a
        picture is never learned for them. Worked out once per catalogue, and kept beside it."""
        index = self.directory / "index.json"
        if not index.exists():
            return frozenset()
        stamp = f"{index.stat().st_mtime_ns}:{index.stat().st_size}:{_item_fixes_stamp()}"
        kept = self.directory / "drawn-identically.json"
        try:
            said = json.loads(kept.read_text(encoding="utf-8"))
            if said.get("stamp") == stamp:
                return frozenset(said["names"])
        except (OSError, ValueError, KeyError):
            pass
        import hashlib

        from PIL import Image

        groups: dict[tuple[int, str], list[str]] = {}
        for entry in self._index.values():
            path = self.directory / str(entry.get("file") or "")
            if not entry.get("file") or not path.is_file():
                continue
            try:
                with Image.open(path) as im:
                    pixels = im.convert("RGBA").resize((32, 32)).tobytes()
            except OSError:
                continue
            key = (int(entry.get("rarity") or 0), hashlib.sha256(pixels).hexdigest())
            groups.setdefault(key, []).append(entry["name"])
        names = sorted(n for group in groups.values() if len(group) > 1 for n in group)
        with contextlib.suppress(OSError):      # worked out again next time: nothing lost
            kept.write_text(json.dumps({"stamp": stamp, "names": names}, ensure_ascii=False),
                            encoding="utf-8")
        return frozenset(names)

    @cached_property
    def _recipe_data(self) -> dict:
        """recipes.json as the wiki gave it, with its known slips put right.

        A resonator's own dish comes from cooking an ordinary one ("使用陆·赫斯烹饪
        浓香熏肉烩炖有概率获得"), so it is made of exactly what that dish is. Where
        its page names an ingredient the game does not have -- 蜜罐 for 黄昏蜜罐,
        禽蛋 for 鸟蛋 -- the ordinary dish's ingredient in the same place, in the
        same amount, is the one that was meant (D110). Names the catalogue knows
        are never touched, and a typo one character off is left to `canonical`.
        """
        path = self.directory / "recipes.json"
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        # The wiki lists what can be made under 可合成道具 -- and leaves a few dishes
        # out of it (菱果炒盐雀, 咸奶茶, 早安，共鸣者, 辛辣脆鸡堡), though each one's own
        # page, fetched with the rest of the bag, says it is a 菜肴 and what goes
        # into it. A page that says so is believed: without this they were in the
        # bag and on no list of dishes (D154).
        listed = {e["name"] for e in data.get("items", [])}
        unlisted = [e for e in data.get("details", [])
                    if e.get("类型") in CRAFTED_TYPES and e["name"] not in listed]
        if unlisted:
            data["items"] = [*data.get("items", []), *unlisted]
        apply_recipe_fixes(data.get("items", []), read_recipe_fixes())
        dishes = {e["name"]: e for e in data.get("items", [])}
        known = set(self._index) | set(dishes)
        for dish in dishes.values():
            base = _COOKED_FROM.search(dish.get("获取途径") or "")
            mine = dish.get("所需材料") or []
            said = base.group(1).strip() if base else ""
            origin = dishes.get(said) or dishes.get(said.strip("「」 "))
            theirs = (origin or {}).get("所需材料")
            if not theirs or len(theirs) != len(mine):
                continue
            dish["所需材料"] = [
                {**m, "name": t["name"]}
                if m["name"] not in known and t["name"] in known and m["amount"] == t["amount"]
                else m
                for m, t in zip(mine, theirs, strict=True)
            ]
        return data

    @cached_property
    def _pages(self) -> dict[str, dict]:
        """name -> the item's wiki page fields (bag items, dishes, potions)."""
        data = self._recipe_data
        pages: dict[str, dict] = {}
        for kind in ("details", "items"):  # a craftable's own page wins
            for entry in data.get(kind, []):
                pages[entry["name"]] = entry
        for name, item in self.overrides["items"].items():  # the user's own word wins
            page = {k: v for k, v in item.items() if k not in ("rarity", "tab")}
            pages[name] = {**pages.get(name, {"name": name}), **page}
        return pages

    @cached_property
    def _recipes(self) -> dict[str, dict]:
        """食谱/配方 name -> its page (where it is found)."""
        return {e["name"]: e for e in self._recipe_data.get("recipes", [])}

    @cached_property
    def _used_in(self) -> dict[str, list[dict]]:
        """ingredient name -> [{name, amount, type}] of every dish/potion that needs it."""
        out: dict[str, list[dict]] = {}
        for item in self._recipe_data.get("items", []):
            for material in item.get("所需材料") or []:
                out.setdefault(self.canonical(material["name"]), []).append(
                    {"name": item["name"], "amount": material["amount"], "type": item.get("类型")}
                )
        return out

    @cached_property
    def _craftables(self) -> list[dict]:
        return self._recipe_data.get("items", [])

    # ----------------------------------------------------------------- lookup

    def page(self, name: str) -> dict:
        """The item's own wiki page fields (类型, 功能, 获取途径 ...), or {}."""
        return self._pages.get(name, {})

    @cached_property
    def builds(self) -> dict:
        """builds.json (tools/fetch_builds.py): what every resonator / weapon costs,
        material names canonical."""
        path = self.directory / "builds.json"
        builds = {"resonators": {}, "weapons": {}}
        if path.exists():
            builds.update(json.loads(path.read_text(encoding="utf-8")))
        apply_build_fixes(builds, read_build_fixes())   # under what the user set by hand
        for name, weapon in self.overrides["weapons"].items():
            builds["weapons"][name] = {**builds["weapons"].get(name, {}), **weapon}
        # A resonator the wiki has no ascension table for yet -- announced but not
        # released -- can be filled in by hand (D74). 心 and 锁暝 are in the
        # catalogue with no materials at all until Kuro publishes them.
        for name, who in self.overrides["resonators"].items():
            builds["resonators"][name] = {**builds["resonators"].get(name, {}), **who}
        for kind in builds.values():  # material names as the catalogue spells them
            for build in kind.values():
                merged: dict[str, int] = {}  # a typo and its true name: summed
                for n, k in (build.get("materials") or {}).items():
                    merged[self.canonical(n)] = merged.get(self.canonical(n), 0) + k
                build["materials"] = merged
        return builds

    @cached_property
    def avatars(self) -> dict:
        """avatars.json (tools/fetch_icons.py): resonator head icons, element icons
        and the 贝币 icon -- only the files that are on disk. The weapon-type icons
        are the app's own drawings and always there (D133)."""
        path = self.directory / "avatars.json"
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        here = self.files_in("avatars")           # listed once, not asked per file (D171)
        found = {table: {k: f for k, f in (data.get(table) or {}).items() if f in here}
                 for table in ("resonators", "elements", "currency")}
        weapons = {}
        for kind, drawn in WEAPON_TYPE_ICONS.items():
            stem = drawn.rsplit(".", 1)[0]
            mine = next((f"{stem}.{ext}" for ext in ("webp", "png") if f"{stem}.{ext}" in here),
                        None)
            shipped = f"{stem}.webp" if (GAME_ICONS / f"{stem}.webp").exists() else None
            weapons[kind] = mine or shipped or drawn
        return {**found, "weapons": weapons}

    @cached_property
    def gids(self) -> dict[str, dict[str, str]]:
        """Game id -> Chinese name, for importing pulls (D53, D135): the names
        shipped with the app, then the ones named by hand on this machine. No id is
        fetched from anywhere, and a list an older version fetched is not read."""
        shipped = read_pull_names()
        out = {kind: {gid: entry["name"] for gid, entry in shipped[kind].items()}
               for kind in ("resonators", "weapons")}
        # weapon ids are 8 digits, resonator ids 4
        for gid, name in self.overrides["gids"].items():
            out["weapons" if len(str(gid)) >= 8 else "resonators"][str(gid)] = name
        return out

    @cached_property
    def pull_english(self) -> dict[str, str]:
        """A weapon's English name, as a pull export writes it -> its name here
        (D135): from the shipped names and the ones given by hand. Kuro's wiki has
        no English name for a weapon, so this is the only place one comes from."""
        shipped = read_pull_names()["weapons"]
        # the game's own name for a weapon first; one somebody named by hand over it
        named = {plain_english(english): name for name, english in read_game_english().items()}
        named.update({plain_english(entry["english"]): entry["name"]
                      for entry in shipped.values() if entry.get("english")})
        mine = self.overrides["gids"]
        for gid, english in self.overrides["pull_english"].items():
            if len(str(gid)) >= 8 and mine.get(gid) and english:
                named[plain_english(english)] = mine[gid]
        named.pop("", None)
        return named

    @cached_property
    def bosses(self) -> dict[str, str]:
        """drop name -> boss portrait file (tools/fetch_bosses.py), files on disk only."""
        path = self.directory / "bosses.json"
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        here = self.files_in("bosses")
        return {k: f for k, f in data.items() if f in here}

    @cached_property
    def shops(self) -> list[dict]:
        """Every shop and what it sells (tools/fetch_shops.py, D158): the game's own
        table. [] before the tool has run.

        A shop that no source names -- not the game's texts, not its map, not the
        wiki -- is left out (D161): a quest's or an event's stall, most likely,
        that nobody could find to buy from. It stays in the file."""
        path = self.directory / "shops.json"
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        return [shop for shop in data.get("shops") or [] if shop.get("name")]

    @staticmethod
    def refresh_of(shop: dict, good: dict) -> str | None:
        """When a good's limit starts over. The wiki's word where its page for the
        shop has one; otherwise weekly for every shop that is not an exchange,
        which the user checked in game (2026-10-14, D161); for an exchange, not
        known."""
        if good.get("refresh"):
            return good["refresh"]
        return None if shop.get("kind") == "exchange" else "每周"

    def shop_icon(self, shop: dict) -> str | None:
        """The shop's picture, if the wiki had one and it was fetched (files on disk only)."""
        file = shop.get("icon")
        return file if file and file in self.files_in("shops") else None

    def sold(self, name: str) -> list[dict]:
        """Where `name` can be bought (D158): per shop what one purchase gives, how
        many purchases the shop allows (None: as many as wanted) and the price.
        The most that can be had first."""
        rows = [{"shop": shop.get("name"), "shop_id": shop["id"], "also": shop.get("also") or [],
                 # what the shop is, for its picture: the wiki's where it has one (D160)
                 "kind": shop.get("kind") or "general", "icon": self.shop_icon(shop),
                 "amount": good["amount"], "limit": good["limit"],
                 "price": [{**p, "icon_file": self.icon_file(p["item"])} for p in good["price"]],
                 "gated": bool(good.get("gated")),
                 # when the limit starts over (D161), and where the shop is
                 "refresh": self.refresh_of(shop, good), "regions": shop.get("regions") or [],
                 "place": shop.get("place")}
                for shop in self.shops for good in shop["goods"] if good["item"] == name]
        return sorted(rows, key=lambda r: (r["limit"] is not None,
                                           -(r["limit"] or 0) * r["amount"], r["shop_id"]))

    @cached_property
    def english_names(self) -> dict[str, tuple[str, str]]:
        """Everything named here -> (its English name, where that came from) (D163).

        Best first: a name a person gave it on the 更新 page (`hand`); the game's own
        English text table (`game`, tools/fetch_english.py); a weapon's from the pulls
        (`pulls`, D135); a resonator's from the wiki's second title (`wiki`)."""
        out: dict[str, tuple[str, str]] = {}
        for name, build in (self.builds.get("resonators") or {}).items():
            if build.get("english"):
                out[name] = (str(build["english"]), "wiki")
        for name, english in self.weapon_english.items():
            out[name] = (english, "pulls")
        path = self.directory / "english.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            game = data.get("names") or {}
            out.update({str(n): (str(e), "game") for n, e in game.items() if e})
        out.update({str(n): (str(e), "hand") for n, e in self.overrides["english"].items() if e})
        return out

    def english(self, name: str | None) -> str | None:
        """A name's English name, or None (D163)."""
        found = self.english_names.get(name or "")
        return found[0] if found else None

    @cached_property
    def weapon_english(self) -> dict[str, str]:
        """A weapon's name here -> its English name, where somebody has named it
        (D135): for showing, and for finding it by (D136)."""
        shipped = read_pull_names()["weapons"]
        out = {name.replace("・", "·"): english for name, english in read_game_english().items()}
        out.update({entry["name"].replace("・", "·"): entry["english"]
                    for entry in shipped.values() if entry.get("english")})
        mine = self.overrides["gids"]
        for gid, english in self.overrides["pull_english"].items():
            if len(str(gid)) >= 8 and mine.get(gid) and english:
                out[mine[gid]] = english
        return out

    def avatar_file(self, name: str) -> str | None:
        """A resonator's head icon. The 漂泊者 forms ("漂泊者-女-衍射") share the
        player character's two icons, by gender."""
        icons = self.avatars["resonators"]
        if name in icons:
            return icons[name]
        if name.startswith("漂泊者"):
            # the wiki's 头像 catalogue names them 女漂泊者 / 男漂泊者
            return icons.get("女漂泊者" if "女" in name else "男漂泊者")
        return None

    def craftables(self) -> list[dict]:
        """Every dish and potion page (可合成道具), as fetched."""
        return self._craftables

    def recipe_source(self, recipe: str) -> str | None:
        """Where a 食谱/配方 is found."""
        page = self._recipes.get(recipe)
        return (page.get("获取途径") or "").strip() or None if page else None

    def names(self) -> list[str]:
        return list(self._index)

    def named(self, text: str) -> str:
        """A name quoted in running text, as the catalogue spells it.

        "使用露帕烹饪「烈日」有概率获得" names a dish that IS called 「烈日」, brackets
        and all; "烹饪「雪莲酥」" would name one that is not. So the text is tried as
        written first, and only then with its brackets off and its typos snapped.
        """
        text = text.strip()
        if text in self._index or any(d["name"] == text for d in self._craftables):
            return text
        return self.canonical(text.strip("「」 "))

    def canonical(self, name: str) -> str:
        """`name` as the catalogue spells it. The wiki's ingredient lists carry the
        odd typo (未啄玉 for 未琢玉); one character off a single real name is it."""
        from .recognize.names import snap

        return snap(name, frozenset(self._index))

    def entry(self, name: str) -> dict | None:
        return self._index.get(name)

    def files_in(self, folder: str = "") -> frozenset[str]:
        """The files of one of the catalogue's folders (D171). On the user's NAS asking the
        disk whether one picture exists took 30-90 ms, and a page asked once per name; so a
        folder is listed, and looked at again at most every LOOK seconds -- re-listed only if
        it changed (a picture the user put there by hand)."""
        listed = self.__dict__.setdefault("_listed", {})
        now = _monotonic()
        held = listed.get(folder)
        if held is not None and now - held[2] < LOOK:
            return held[0]
        path = self.directory / folder
        try:
            stamp = path.stat().st_mtime_ns
        except OSError:
            stamp = None
        if held is not None and held[1] == stamp:
            listed[folder] = (held[0], stamp, now)
            return held[0]
        try:
            with os.scandir(path) as entries:
                names = frozenset(e.name for e in entries)
        except OSError:
            names = frozenset()
        listed[folder] = (names, stamp, now)
        return names

    def icon_file(self, name: str) -> str | None:
        entry = self._index.get(name)
        file = entry.get("file") if entry else None
        return file if file and file in self.files_in() else None

    def detail(self, name: str) -> dict:
        """Everything known about one item, for the detail panel."""
        page = {k: v.strip() if isinstance(v, str) else v
                for k, v in self._pages.get(name, {}).items() if k != "entry_id"}
        if page.get("所需材料"):
            page["所需材料"] = [
                {**m, "name": self.canonical(m["name"]),
                 "icon_file": self.icon_file(self.canonical(m["name"])),
                 "rarity": (self._index.get(self.canonical(m["name"])) or {}).get("rarity")}
                for m in page["所需材料"]
            ]
        entry = self._index.get(name) or {}
        unlock = page.get("食谱解锁") or page.get("配方解锁")
        recipe = self._recipes.get(unlock) if unlock else None
        return {
            "name": name,
            "icon_file": self.icon_file(name),
            "rarity": entry.get("rarity"),
            "tab": entry.get("tab"),
            "page": page,
            # Highest tier first, then by name: 面粉 goes into 48 dishes, and the
            # question asked of that list is "which of the good ones" (D100).
            "used_in": sorted(
                ({**u, "icon_file": self.icon_file(u["name"]),
                  "rarity": (self._index.get(u["name"]) or {}).get("rarity")}
                 for u in self._used_in.get(name, [])),
                key=lambda u: (-(u["rarity"] or 0), u["name"]),
            ),
            "recipe": (
                {"name": unlock, "source": recipe.get("获取途径") if recipe else None}
                if unlock else None
            ),
        }
