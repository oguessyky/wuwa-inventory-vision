# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""What the user owns now, merged from every scan (D45 decisions 3, 5, 13).

Each scan is a snapshot of one bag tab. "Owned" is the newest reading of each
item across all of them:

* Named items merge across scans by name; the newest scan that saw an item wins.
* An unnamed item cannot be matched across scans, so only its tab's newest scan
  counts for it.
* An item absent from a newer COMPLETE scan of its tab (the game's header count
  matched) was used up: owned 0 -- but only when that scan named everything it
  saw. An unnamed tile in it might be the item, and 0 would then be a lie.
* A count corrected by hand is the newest reading until a later scan reads that
  item again.
* Names with no Chinese in them are leftovers of the English reference set that
  D42 replaced ("Cadence Blossom"), not identities: such readings count as
  unnamed. Kept as names, they never matched the Chinese names of newer scans and
  81 items read as used up.
* One item can sit in SEVERAL stacks (D60): the bag caps a stack at 9999, so
  特级调谐器 shows as 9999 + 9999 + 4606 tiles. They stitch as distinct items --
  identity is grid position -- so the owned count is their SUM. Observations
  always hold a tile's own count (a panel read stores the tile's count, not the
  panel's 拥有), so summing them never double-counts the total.
* Only the bag tabs the scanner reads (资源, 素材, 补给) are shown.

Headless: the main app renders the result; nothing here knows about HTTP.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .catalogue import Catalogue
from .recognize.names import weapon_names
from .store.db import Store

#: Bag tabs the main app shows (the scanner skips 声骸, 任务, 武器, 特殊).
BAG_TABS = ("资源", "素材", "补给")
#: The 武器 tab is weapons, one per tile -- but the weapon EXP materials (the four
#: 能源核心) live there too, as ordinary counted tiles, and nowhere else (D104).
WEAPON_TAB = "武器"


@dataclass
class Item:
    ident: str
    """The item's name, or "key:<item_key>" while nobody has named it."""
    name: str | None
    tab: str | None
    rarity: int
    count: int | None
    source: str
    """scan | manual | used-up | none (catalogue item never seen)."""
    seen_at: str | None
    """When the count was read (scan start) or set by hand; None if never seen."""
    scan_id: int | None
    icon_key: str | None
    """Scanned crop to show when there is no catalogue art (/api/icon/<key>.webp)."""
    icon_file: str | None
    """Catalogue art file, when data/catalogue is downloaded."""
    stacks: list[int]
    """Per-stack counts when the item spans more than one tile (D60); else []."""
    rivals: list[str]
    """Looks identical to these named items: the user must click it (待确认)."""
    delta: int | None = None
    """Change against the previous scan that saw it (D68); None: first sighting."""
    fresh: bool = False
    """Read by the newest scan of its tab -- so its count is from just now."""

    @property
    def pending(self) -> bool:
        return self.name is None

    def as_dict(self) -> dict:
        return {**asdict(self), "pending": self.pending}


def _readings(store: Store) -> list[dict]:
    """One row per (scan, stitched item): its best-confidence reading."""
    rows = store.conn.execute(
        """SELECT o.scan_id, s.tab_label AS tab, s.started_at,
                  COALESCE(o.item_key, o.icon_hash) AS key,
                  MAX(o.item_name) AS name, MAX(o.rarity) AS rarity,
                  (SELECT o2.count FROM observation o2
                    WHERE o2.scan_id = o.scan_id
                      AND COALESCE(o2.item_key, o2.icon_hash)
                          = COALESCE(o.item_key, o.icon_hash)
                      AND o2.count IS NOT NULL
                    ORDER BY o2.count_conf DESC LIMIT 1) AS count,
                  MAX(o.rivals) AS rivals, MAX(o.level) AS level
             FROM observation o JOIN scan s ON s.id = o.scan_id
            WHERE s.tab_label IS NOT NULL
         GROUP BY o.scan_id, COALESCE(o.item_key, o.icon_hash)"""
    ).fetchall()
    out = []
    for row in rows:
        r = dict(row)
        # A 武器-tab tile with no level is not a weapon: it is a counted item that
        # happens to sit there, and it is owned like anything else in the bag.
        level = r.pop("level")
        stocked = (r["tab"] == WEAPON_TAB and level is None and r["name"] and r["count"]
                   and r["name"] not in weapon_names())
        if r["tab"] not in BAG_TABS and not stocked:
            continue
        if r["name"] and not _has_cjk(r["name"]):
            r["name"] = None  # a legacy English reference name
        out.append(r)
    return out


def _deltas(readings: list[dict]) -> dict[str, int]:
    """Per NAME: how much its count moved in its newest scan (D68).

    "What changed since last time" is the one thing a fresh scan has to say, and
    it is only knowable here: the store keeps every scan, so the reading before
    the newest one is still there.
    """
    history: dict[str, list[dict]] = {}
    for r in sorted(readings, key=lambda r: r["scan_id"]):
        if r["name"] and r["count"] is not None:
            history.setdefault(r["name"], []).append(r)
    out = {}
    for name, seen in history.items():
        if len(seen) >= 2 and seen[-1]["scan_id"] != seen[-2]["scan_id"]:
            out[name] = seen[-1]["count"] - seen[-2]["count"]
    return out


def _merge_stacks(readings: list[dict]) -> list[dict]:
    """Fold a scan's several stacks of one item into a single reading (D60).

    Unnamed readings cannot be folded -- nothing says two unnamed tiles are the
    same item -- so they pass through untouched.
    """
    out: list[dict] = []
    head_of: dict[tuple[int, str], dict] = {}
    for row in readings:
        r = dict(row, stacks=[] if row["count"] is None else [row["count"]])
        head = head_of.get((r["scan_id"], r["name"])) if r["name"] else None
        if head is None:
            if r["name"]:
                head_of[(r["scan_id"], r["name"])] = r
            out.append(r)
            continue
        if r["count"] is not None:
            head["count"] = (head["count"] or 0) + r["count"]
            head["stacks"] += r["stacks"]
        rivals = "|".join(x for x in (head["rivals"], r["rivals"]) if x)
        head["rivals"] = "|".join(dict.fromkeys(rivals.split("|"))) or None
    for r in out:
        if len(r["stacks"]) < 2:
            r["stacks"] = []  # one tile: there is nothing to break down
    return out


def _has_cjk(text: str) -> bool:
    return any("一" <= ch <= "鿿" for ch in text)


def _complete_scans(store: Store) -> dict[str, tuple[int, set[str]]]:
    """tab -> (id of its newest complete, fully named scan, names it contained)."""
    out: dict[str, tuple[int, set[str]]] = {}
    for scan in store.conn.execute(
        """SELECT s.id, s.tab_label, s.header_total,
                  (SELECT COUNT(DISTINCT COALESCE(item_key, icon_hash)) FROM observation
                    WHERE scan_id = s.id) AS found
             FROM scan s WHERE s.tab_label IS NOT NULL ORDER BY s.id"""
    ):
        if scan["header_total"] is None or scan["found"] != scan["header_total"]:
            continue
        unnamed = store.conn.execute(
            """SELECT COUNT(*) FROM (SELECT COALESCE(item_key, icon_hash) FROM observation
                WHERE scan_id = ? GROUP BY COALESCE(item_key, icon_hash)
               HAVING MAX(item_name) IS NULL)""", (scan["id"],)
        ).fetchone()[0]
        if unnamed:
            continue
        names = {
            r[0] for r in store.conn.execute(
                "SELECT DISTINCT item_name FROM observation WHERE scan_id = ? "
                "AND item_name IS NOT NULL", (scan["id"],)
            ) if _has_cjk(r[0])
        }
        out[scan["tab_label"]] = (scan["id"], names)
    return out


def build_inventory(store: Store, catalogue: Catalogue, show_all: bool = False) -> list[Item]:
    """Everything owned, newest reading first per item; plus the whole catalogue if `show_all`."""
    readings = _merge_stacks(_readings(store))
    moved = _deltas(readings)
    newest_scan_of_tab: dict[str, int] = {}
    for r in readings:
        newest_scan_of_tab[r["tab"]] = max(newest_scan_of_tab.get(r["tab"], 0), r["scan_id"])

    latest: dict[str, dict] = {}
    for r in sorted(readings, key=lambda r: r["scan_id"]):
        if r["name"]:
            latest[r["name"]] = r  # later scans overwrite earlier ones
        elif r["scan_id"] == newest_scan_of_tab[r["tab"]]:
            latest[f"key:{r['key']}"] = r

    complete = _complete_scans(store)
    manual = store.manual_counts()
    items: dict[str, Item] = {}
    for ident, r in latest.items():
        name = r["name"]
        entry = catalogue.entry(name) if name else None
        item = Item(
            # shown under the catalogue's tab; the scan's own tab still decides
            # below whether a newer complete scan says it is used up
            ident=ident, name=name,
            tab=(entry or {}).get("tab") or r["tab"] if r["tab"] == WEAPON_TAB else r["tab"],
            rarity=int((entry or {}).get("rarity") or r["rarity"] or 0),
            count=r["count"], source="scan", seen_at=r["started_at"], scan_id=r["scan_id"],
            icon_key=r["key"], icon_file=catalogue.icon_file(name) if name else None,
            stacks=sorted(r.get("stacks") or [], reverse=True),
            rivals=[x for x in (r["rivals"] or "").split("|") if x],
            delta=moved.get(name) if name else None,
            fresh=r["scan_id"] == newest_scan_of_tab.get(r["tab"]),
        )
        done = complete.get(r["tab"])
        if name and done and done[0] > r["scan_id"] and name not in done[1]:
            item.count, item.source, item.stacks = 0, "used-up", []
        if ident in manual and manual[ident][1] > (item.seen_at or ""):
            item.count, item.source, item.seen_at = manual[ident][0], "manual", manual[ident][1]
            item.stacks = []  # a hand-set total says nothing about the stacks
        items[ident] = item

    if show_all:
        for name in catalogue.names():
            entry = catalogue.entry(name) or {}
            if name in items or entry.get("tab") not in BAG_TABS:
                continue
            count, source, seen = 0, "none", None
            if name in manual:
                count, source, seen = manual[name][0], "manual", manual[name][1]
            items[name] = Item(
                ident=name, name=name, tab=entry.get("tab"), rarity=int(entry.get("rarity") or 0),
                count=count, source=source, seen_at=seen, scan_id=None, icon_key=None,
                icon_file=catalogue.icon_file(name), stacks=[], rivals=[],
            )
    return sorted(
        items.values(),
        key=lambda i: (BAG_TABS.index(i.tab) if i.tab in BAG_TABS else 9, -i.rarity,
                       i.source == "none", i.name or "~"),
    )


def tab_summary(store: Store) -> list[dict]:
    """Per bag tab: its newest scan's progress, for the tab chips."""
    out = []
    for r in store.latest_scans_by_tab():
        if r["tab_label"] not in BAG_TABS:
            continue  # the 武器 tab is scanned too (D56), but it is not a bag of counts
        out.append({
            "tab": r["tab_label"], "scan_id": r["id"], "scanned_at": r["started_at"],
            "found": r["found"], "total": r["header_total"],
            "complete": r["header_total"] is not None and r["found"] == r["header_total"],
        })
    return out
