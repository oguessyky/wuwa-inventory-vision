# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""What to buy (D158): the things kept below their base amount, and where to get them.

A base amount is the user's own floor under an item a shop sells: "have at least
this many". It is a second number beside the item's target (D84), which still
replaces what the builds and dishes work out; the base is then the least the
target can be. Where each item is sold, how many a shop allows and for how much
is the game's own table (`Catalogue.sold`, tools/fetch_shops.py).

**One round of the shops.** The table gives a shop's limit and not when it
starts over, and the app never sees what was already bought. So a plan here is
one round: every shop at its full limit, cheapest first. What one round cannot
cover is said as `left` -- to be bought when the limits have started over.

Headless: the pages render what this returns.
"""

from __future__ import annotations

import math

from . import exp
from .catalogue import Catalogue
from .store.db import ECHO_BASE as ECHOES

#: The currency a price is compared in. A good priced in anything else, or in two
#: things at once, cannot be ranked against it and is bought last.
COIN = "贝币"


def _per_piece(row: dict) -> tuple[int, float]:
    price = row["price"]
    if len(price) == 1 and price[0]["item"] == COIN:
        return (0, price[0]["amount"] / max(row["amount"], 1))
    return (1, 0.0)


def one_round(rows: list[dict], want: int) -> dict:
    """Buy `want` of an item from `rows` (`Catalogue.sold`), cheapest first, no
    shop past its limit: {buys, pieces, left, cost}.

    A purchase can give more than one piece, so the last one may bring a few
    more than were wanted; `pieces` is what is actually bought. A good that has
    to be unlocked is bought like any other and marked: whether it is unlocked
    is not something this app can see.
    """
    left, buys, cost = max(want, 0), [], {}
    for index, row in sorted(enumerate(rows),
                             key=lambda ir: (*_per_piece(ir[1]), ir[1]["shop_id"])):
        if left <= 0:
            break
        purchases = math.ceil(left / max(row["amount"], 1))
        if row["limit"] is not None:
            purchases = min(purchases, row["limit"])
        if purchases <= 0:
            continue
        pieces = purchases * row["amount"]
        paid = [{"item": p["item"], "amount": p["amount"] * purchases} for p in row["price"]]
        for p in paid:
            cost[p["item"]] = cost.get(p["item"], 0) + p["amount"]
        buys.append({"row": index, "shop": row["shop"], "shop_id": row["shop_id"],
                     "purchases": purchases,
                     "pieces": pieces, "cost": paid, "gated": row["gated"],
                     "kind": row.get("kind") or "general", "icon": row.get("icon"),
                     "regions": row.get("regions") or [], "place": row.get("place")})
        left -= pieces
    return {"buys": buys, "pieces": sum(b["pieces"] for b in buys), "left": max(left, 0),
            "cost": [{"item": k, "amount": v} for k, v in cost.items()]}


def to_buy(catalogue: Catalogue, owned: dict[str, int], bases: dict[str, int]) -> list[dict]:
    """Every item below its base amount, the shortest of its base first:
    {name, rarity, icon_file, owned, base, short, plan}. An item no shop sells
    any more keeps its base and has an empty plan."""
    out = []
    for name, base in bases.items():
        have = owned.get(name, 0)
        if base <= have:
            continue
        entry = catalogue.entry(name) or {}
        out.append({"name": name, "rarity": int(entry.get("rarity") or 0),
                    "icon_file": catalogue.icon_file(name), "owned": have, "base": base,
                    "short": base - have,
                    "plan": one_round(catalogue.sold(name), base - have)})
    return sorted(out, key=lambda r: (r["owned"] / r["base"], r["name"]))


def trips(rows: list[dict]) -> list[dict]:
    """`to_buy`, turned round: per shop what to buy there this round (D160). The
    dashboard draws a shop with the things to pick up in it, which is how a
    shopping round is walked; the most pieces first.

    {shop, shop_id, kind, icon, regions, place, cost, goods: [{name, rarity, icon_file, pieces}]}
    -- where the shop is (D177), as the 商店 page says it: the map's marks, else the wiki's place
    """
    out: dict[int, dict] = {}
    for row in rows:
        for buy in row["plan"]["buys"]:
            trip = out.setdefault(buy["shop_id"], {
                "shop": buy["shop"], "shop_id": buy["shop_id"], "kind": buy["kind"],
                "icon": buy["icon"], "regions": buy.get("regions") or [],
                "place": buy.get("place"), "cost": {}, "goods": []})
            trip["goods"].append({"name": row["name"], "rarity": row["rarity"],
                                  "icon_file": row["icon_file"], "pieces": buy["pieces"],
                                  "gated": buy["gated"]})
            for paid in buy["cost"]:
                trip["cost"][paid["item"]] = trip["cost"].get(paid["item"], 0) + paid["amount"]
    for trip in out.values():
        trip["cost"] = [{"item": k, "amount": v} for k, v in trip["cost"].items()]
    return sorted(out.values(), key=lambda t: (-sum(g["pieces"] for g in t["goods"]), t["shop_id"]))


def listing(catalogue: Catalogue, owned: dict[str, int], bases: dict[str, int]) -> list[dict]:
    """Every shop with what it sells, for the 商店 page (D160): each good with its
    picture, what is owned of it and the base amount it was given, and each
    price with the picture of what it is paid in where the catalogue has one."""
    tubes = {i["name"] for i in exp.items(catalogue, "echo")}
    if tubes and ECHOES in bases:
        bases = {**bases, **{t: bases[ECHOES] for t in tubes}}
    out = []
    for shop in catalogue.shops:
        goods = []
        for good in shop["goods"]:
            entry = catalogue.entry(good["item"]) or {}
            goods.append({
                "name": good["item"], "rarity": int(entry.get("rarity") or 0),
                "icon_file": catalogue.icon_file(good["item"]),
                "amount": good["amount"], "limit": good["limit"],
                "refresh": catalogue.refresh_of(shop, good),
                "gated": bool(good.get("gated")),
                "price": [{**p, "icon_file": catalogue.icon_file(p["item"])}
                          for p in good["price"]],
                "owned": owned.get(good["item"], 0), "base": bases.get(good["item"], 0),
                # a tube's base is the echoes' (D161): counted in +25 echoes, not pieces
                "echo": good["item"] in tubes,
            })
        out.append({"id": shop["id"], "name": shop.get("name"), "also": shop.get("also") or [],
                    "kind": shop.get("kind") or "general", "icon": catalogue.shop_icon(shop),
                    "place": shop.get("place"), "npc": shop.get("npc"),
                    "regions": shop.get("regions") or [],
                    "paid_in": sorted({p["item"] for g in shop["goods"] for p in g["price"]}),
                    "goods": goods})
    return out


def echo_gap(catalogue: Catalogue, owned: dict[str, int], echoes: int) -> dict | None:
    """密音筒's base, which is counted in echoes (D161): enough EXP, from all four
    tubes together, for `echoes` five-star echoes from +0 to +25.

    {echoes, each, points, have, short_points, short_echoes, exchanges,
    exchange_points}. Below it there is no round of buying: every tube a shop
    sells is in an exchange, each paid in its own currency, so there is no
    cheapest first; `exchanges` is each of them with what its limit would add,
    and `exchange_points` all of it together. None with no base or no table."""
    each = exp.needed(catalogue, "echo", 5, 0, 25)
    tubes = exp.items(catalogue, "echo")
    if not echoes or not each or not tubes:
        return None
    points = sum(t["value"] * owned.get(t["name"], 0) for t in tubes)
    short = max(echoes * each - points, 0)
    exchanges = []
    for tube in tubes:
        for row in catalogue.sold(tube["name"]):
            pieces = row["limit"] * row["amount"] if row["limit"] is not None else None
            exchanges.append({
                "shop": row["shop"], "shop_id": row["shop_id"], "kind": row["kind"],
                "icon": row["icon"], "item": tube["name"], "rarity": tube["rarity"],
                "icon_file": tube["icon_file"], "pieces": pieces, "price": row["price"],
                "exp": pieces * tube["value"] if pieces is not None else None,
                "refresh": row["refresh"], "gated": row["gated"]})
    exchanges.sort(key=lambda e: (-(e["exp"] or 0), e["shop_id"]))
    return {"echoes": echoes, "each": each, "points": points, "have": points // each,
            "short_points": short, "short_echoes": math.ceil(short / each),
            "exchanges": exchanges,
            "exchange_points": sum(e["exp"] or 0 for e in exchanges)}
