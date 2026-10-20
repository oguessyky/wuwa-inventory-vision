# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""The cooking/crafting stock view (D45 decisions 6-8).

For every dish and potion: how many are owned against the amount the user wants
kept, and whether more can be made now. The page's main job is the ones BELOW
their target.

* Target: a per-item override, else the default for its type (菜肴 / 药品),
  both set by the user. 0 means "not tracked".
* Can make now: min(owned // needed) over its ingredients. None when it cannot be
  made directly -- a signature dish (特色料理) only comes by chance when one
  character cooks another dish, and some potions are only bought.
* Learned: 食谱/配方 are ticked by hand (the bag scan cannot see them). "默认解锁",
  and a 食谱/配方 found "默认学习"/"默认获得", is always learned; a dish whose page
  names no 食谱 needs none.

Headless: the main app renders what this returns.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from . import effects
from .catalogue import Catalogue
from .inventory import Item
from .store.db import Store

#: Default targets per type until the user sets their own (D45 decision 8).
DEFAULT_TARGETS = {"菜肴": 10, "药品": 5}
TYPES = tuple(DEFAULT_TARGETS)
#: A signature dish's source: "使用吟霖烹饪碎金饭有概率烹饪获得".
#: The wiki doubles the verb on some pages ("使用炽霞烹饪烹饪今州冒菜有概率获得"), and leaves
#: out the chance on others ("使用卜灵烹饪清芬鱼汤获得", D172).
_SIGNATURE = re.compile(r"使用(.+?)烹饪(?:烹饪)?(.+?)(?:有概率|获得)")
#: Whose dish it is, as the page's 是否为特色料理 says: "嘉贝莉娜特色料理", "卜灵的特色料理" --
#: on some pages the only place that says so (超级加倍特浓奶昔刨冰: 获取途径 "烹饪获得", D172).
_WHOSE = re.compile(r"(.+?)的?特色料理")
#: A recipe that came from a collaboration (必胜客, 肯德基, 罗森...): most players never had it,
#: and nobody can get it now (D172).
COLLAB = "联动"
ALWAYS_LEARNED = "默认解锁"


@dataclass
class Craftable:
    name: str
    type: str
    rarity: int
    effect: str | None
    owned: int
    target: int
    target_is_default: bool
    makeable: int | None
    """How many can be made from owned ingredients; None if it cannot be made directly."""
    ingredients: list[dict] = field(default_factory=list)
    recipe: str | None = None
    """The 食谱/配方 that teaches it (None: needs none)."""
    learned: bool = True
    recipe_source: str | None = None
    signature: dict | None = None
    """{"character", "base"} for a 特色料理: cook `base` as `character` for a chance."""
    limited: bool = False
    """Its recipe came from a collaboration (D172): not tracked unless it was learned."""
    source: str | None = None
    icon_file: str | None = None
    known: bool = False
    """The count is real: read by a scan or a hand fix, or 0 because the tab's
    newest complete scan did not contain it. False: its tab is not fully scanned
    yet, so 0 may just mean "not seen"."""
    missing: str | None = None
    """The resonator who has to cook it, when they are not on the account: it
    cannot be made at all then, whatever is in stock (D126)."""
    effects: dict | None = None
    """`effect` taken apart (`effects.Effect`): what changes, by how much, for how
    long. None when the sentence says nothing the reader knows (D114)."""

    @property
    def shortfall(self) -> int:
        return max(self.target - self.owned, 0)

    def as_dict(self) -> dict:
        return {**asdict(self), "shortfall": self.shortfall}


def default_targets(store: Store) -> dict[str, int]:
    return {t: int(store.setting(f"target:{t}", str(n))) for t, n in DEFAULT_TARGETS.items()}


def _type_of(page: dict) -> str:
    kind = page.get("类型")
    if kind in TYPES:
        return kind
    # A few pages have no 类型 row and no unlock to infer it from (the 干涉混悬液).
    return "药品" if "药" in (page.get("获取途径") or "") else "菜肴"


#: The bag tab dishes and potions sit in.
CRAFT_TAB = "补给"


def ingredient_needs(items: list[Craftable]) -> dict[str, int]:
    """Per ingredient: how much every dish still below its target would take.

    A 特产 nothing needs for a build can still be wanted for cooking (D58).
    """
    out: dict[str, int] = {}
    for craftable in items:
        for ingredient in craftable.ingredients:
            take = ingredient["amount"] * craftable.shortfall
            if take:
                out[ingredient["name"]] = out.get(ingredient["name"], 0) + take
    return out


def ingredient_sources(items: list[Craftable]) -> dict[str, list[dict]]:
    """Per ingredient: the dishes below their target that want it, and how much each
    takes -- `ingredient_needs`, itemised, so a target can say where it comes from (D122)."""
    out: dict[str, list[dict]] = {}
    for craftable in items:
        for ingredient in craftable.ingredients:
            take = ingredient["amount"] * craftable.shortfall
            if take:
                out.setdefault(ingredient["name"], []).append({
                    "name": craftable.name, "rarity": craftable.rarity,
                    "icon_file": craftable.icon_file, "per": ingredient["amount"],
                    "short": craftable.shortfall, "amount": take,
                })
    for rows in out.values():
        rows.sort(key=lambda r: (-r["amount"], r["name"]))
    return out


def _whose(page: dict) -> str | None:
    """The resonator whose own dish this is, as 是否为特色料理 says; None for anyone's."""
    said = (page.get("是否为特色料理") or "").strip()
    found = _WHOSE.fullmatch(said) if said and said != "否" else None
    return found.group(1).strip() if found else None


#: Every form of the 漂泊者 cooks as "漂泊者".
_ROVER = "漂泊者"


def build_cooking(
    store: Store, catalogue: Catalogue, inventory: list[Item], tab_complete: bool = False,
    cooks: set[str] | frozenset[str] | None = None,
) -> list[Craftable]:
    """`tab_complete`: the 补给 tab's newest scan matched the game's header count.

    `cooks`: the resonators on the account. A resonator's own dish only comes
    out when THEY cook, so without them it cannot be made (D126): it is not
    tracked unless the user gives it a target, and it asks for no ingredients.
    A few may sit in the bag all the same -- the story hands some out. None
    (the default) leaves every dish makeable, for callers that do not know.
    """
    on_account = None if cooks is None else {
        _ROVER if name.startswith(_ROVER) else name for name in cooks}
    owned = {i.name: i for i in inventory if i.name}
    defaults = default_targets(store)
    overrides = store.craft_targets()
    learned = store.learned_recipes()
    # the ordinary dish each 食谱 teaches: a resonator's dish that names only whose it is
    # (是否为特色料理) is that dish, cooked by them (D172)
    ordinary: dict[str, str] = {}
    for page in catalogue.craftables():
        teaches = page.get("食谱解锁") or page.get("配方解锁")
        if teaches and not _whose(page) and not _SIGNATURE.search(page.get("获取途径") or ""):
            ordinary.setdefault(teaches, page["name"])

    out = []
    for page in catalogue.craftables():
        name = page["name"]
        kind = _type_of(page)
        mine = owned.get(name)
        have = (mine.count or 0) if mine else 0

        ingredients = []
        for m in page.get("所需材料") or []:
            ing = catalogue.canonical(m["name"])
            item = owned.get(ing)
            ingredients.append({
                "name": ing, "amount": m["amount"],
                "owned": (item.count or 0) if item else 0,
                "icon_file": catalogue.icon_file(ing),
            })

        source = (page.get("获取途径") or "").strip() or None
        match = _SIGNATURE.search(source or "")
        # the base dish as the catalogue calls it (some ARE called with their 「」)
        signature = ({"character": match.group(1),
                      "base": catalogue.named(match.group(2))}
                     if match else None)
        if signature is None and (cook_named := _whose(page)):
            teaches = page.get("食谱解锁") or page.get("配方解锁")
            signature = {"character": cook_named, "base": ordinary.get(teaches or "")}
        makeable = None
        if ingredients and not signature:
            makeable = min(i["owned"] // i["amount"] for i in ingredients)

        # A resonator's own dish is not learned: it is what comes out, by chance,
        # when they cook the base dish, and the 食谱 its page names is the base
        # dish's. So it has none of its own -- no 未学会 on it, nothing to tick (D123).
        recipe = None if signature else page.get("食谱解锁") or page.get("配方解锁") or None
        recipe_source = catalogue.recipe_source(recipe) if recipe else None
        if recipe and recipe_source is None:
            # the dish's page names it shorter than its own page does: "“街角邂逅”食谱" for
            # "“街角邂逅”巧克力礼盒食谱" (D172)
            recipe_source = catalogue.recipe_source(name + recipe[-2:])
        # "默认学习" / "默认获得": everyone knows it from the start.
        default = recipe == ALWAYS_LEARNED or "默认" in (recipe_source or "")
        entry = catalogue.entry(name) or {}
        rarity = entry.get("rarity") or int((page.get("品质") or "0")[:1] or 0)
        cook = signature["character"] if signature else None
        missing = cook if cook and on_account is not None and cook not in on_account else None
        knows = recipe is None or default or recipe in learned
        limited = COLLAB in (recipe_source or "")
        # nobody to cook it, or a collaboration's recipe never learned: not something to stock
        # up on, unless the user says so
        target = overrides.get(name, 0 if missing or (limited and not knows) else defaults[kind])
        effect = (page.get("功能") or "").strip() or None
        parts = effects.parse(effect)
        out.append(Craftable(
            name=name, type=kind, rarity=int(rarity or 0),
            effect=effect, effects=parts.as_dict() if parts else None,
            owned=have, target=target, target_is_default=name not in overrides,
            makeable=makeable, ingredients=ingredients,
            recipe=None if default else recipe,
            learned=knows,
            recipe_source=recipe_source,
            signature=signature, limited=limited, source=source, missing=missing,
            icon_file=catalogue.icon_file(name), known=mine is not None or tab_complete,
        ))
    return out
