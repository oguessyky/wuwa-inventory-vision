# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""The dashboard (D159): three questions answered at a glance.

* What can I pay for? -- the wallet as last read, and how far the EXP items go.
* What am I short of? -- what to buy, the dishes below their targets, what the
  plans still lack.
* Can I trust the numbers? -- each tab's last scan, what is still waiting for a
  name, and on a scanner the scans not yet sent home.

Nothing here is worked out for the first time: every number is one another page
already shows, from the module that owns it (`exp`, `shops`, `cooking`,
`planner`, `inventory`). This only chooses and cuts them down to a card each.
Nothing is set on the dashboard either; a card leads to the page that owns it.

Headless: the page renders what this returns.
"""

from __future__ import annotations

from . import exp, shops
from .catalogue import Catalogue
from .inventory import BAG_TABS

#: A group shows this many tiles and says how many more there are: two rows of
#: them on a wide window (D160; it was six lines of text before).
ROWS = 12
KINDS = ("resonator", "weapon", "echo")


def pay(catalogue: Catalogue, owned: dict[str, int], wallet: dict | None,
        echoes: int = 0) -> dict:
    """The wallet, and per kind of build what the EXP items owned are worth
    (`exp.tiers`): a resonator and a five-star weapon to the top, a five-star
    echo to each of its five tiers (D157). A kind with no level table has no
    tiers, and one with no EXP item in the catalogue is left out."""
    stock = []
    for kind in KINDS:
        items = exp.items(catalogue, kind)
        if not items:
            continue
        points = sum(i["value"] * owned.get(i["name"], 0) for i in items)
        stock.append({
            "kind": kind, "owned_points": points, "tiers": exp.tiers(catalogue, kind, points),
            # echoes: the base set for them, and how far below it (D161)
            "gap": shops.echo_gap(catalogue, owned, echoes) if kind == "echo" else None,
            "items": [{"name": i["name"], "rarity": i["rarity"], "icon_file": i["icon_file"],
                       "owned": owned.get(i["name"], 0)} for i in items],
        })
    return {"wallet": wallet, "exp": stock}


def _cut(rows: list[dict]) -> dict:
    return {"count": len(rows), "rows": rows[:ROWS]}


def short(to_buy: list[dict], dishes: list[dict], plans: dict,
          materials: list[dict] | None = None) -> dict:
    """What is missing, four ways.

    `to_buy`: `shops.to_buy` -- everything below its base amount (D158).
    `dishes`: `Craftable.as_dict` rows; kept are the ones below a target that can
    be cooked on this account, the most servings short first.
    `plans`: `planner.view`; kept are the materials all plans together still lack.
    `materials`: 材料's groups (`MaterialGroup.as_dict`, D181); kept are the tiers it marks
    缺 N -- short after synthesis, against the targets set there -- the most short first.
    """
    tiers = sorted((t for g in materials or [] for t in g.get("tiers") or []
                    if t.get("shortfall", 0) > 0),
                   key=lambda t: (-t["shortfall"], t["name"]))
    below = sorted((d for d in dishes if d["shortfall"] > 0 and not d.get("missing")),
                   key=lambda d: (-d["shortfall"], d["name"]))
    lacking = sorted((m for m in plans.get("materials") or [] if m["shortfall"] > 0),
                     key=lambda m: (-m["rarity"], -m["shortfall"], m["name"]))
    return {
        "buy": {**_cut(to_buy), "trips": shops.trips(to_buy)},
        "dishes": _cut([{k: d[k] for k in ("name", "rarity", "icon_file", "owned", "target",
                                           "shortfall", "makeable")} for d in below]),
        "materials": _cut([{k: t[k] for k in ("name", "rarity", "icon_file", "owned", "target",
                                              "shortfall")} for t in tiers]),
        "plans": {**_cut([{k: m[k] for k in ("name", "rarity", "icon_file", "owned", "target",
                                             "shortfall")} for m in lacking]),
                  "plans": len(plans.get("plans") or []),
                  # who the plans are for, as the page draws them: a face or a weapon
                  "who": [{"kind": p["kind"], "name": p["name"], **(p.get("who") or {})}
                          for p in (plans.get("plans") or [])[:ROWS]]},
    }


def trust(tabs: list[dict], inventory: list, unsent: dict | None) -> dict:
    """Whether the numbers can be believed.

    `tabs`: `inventory.tab_summary` -- every bag tab is listed, one never scanned
    included, in the bag's own order. `inventory`: the items; counted are the ones
    still waiting to be told apart or named (`pending`). `unsent`: {count, home}
    on a scanner with a home, None anywhere else.
    """
    by_tab = {t["tab"]: t for t in tabs}
    waiting = [i for i in inventory if getattr(i, "pending", False)]
    return {
        "tabs": [{"tab": tab, "scanned": tab in by_tab,
                  **{k: by_tab.get(tab, {}).get(k) for k in ("scanned_at", "found", "total")},
                  "complete": bool(by_tab.get(tab, {}).get("complete"))} for tab in BAG_TABS],
        "pending": len(waiting),
        "unsent": unsent,
    }
