# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""What the 武器 tab scan says about the weapons the user owns (D62).

Weapons never stack: one tile is one copy, with its own level, its own 谐振阶数
and -- from the portrait in its corner -- its own holder. 飞逝 sat on seven tiles
in one scan, six at 精1 and one at 精5, equipped (D63).

That makes the scan the honest answer to "can this reach 精5": merging every copy
still in the bag adds their ranks up (`roster.reachable_rank`), where the pull
history only says how many were ever pulled.

Names for the portraits come from the user (D61): a face the scan has not been
told about is listed here as "unnamed" for the 武器 page to ask about, never
guessed at.

Headless: the main app renders what this returns.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .roster import MAX_RANK, ROVER, reachable_rank
from .store.db import Store

WEAPON_TAB = "武器"


@dataclass
class Copy:
    """One 武器 tile: one copy of a weapon, at a level and a 谐振阶数."""

    key: str
    name: str | None
    level: int | None
    rank: int
    """谐振阶数 1-5: the number the tile shows, which is NOT a quantity (D63)."""
    holder_key: str | None = None
    holder: str | None = None
    """Who is carrying it -- only ever a name the user gave that face."""

    def as_dict(self) -> dict:
        return {**asdict(self), "equipped": self.holder_key is not None}


def latest_scan(store: Store) -> dict | None:
    """The newest 武器 scan: its id, when it ran, and how complete it was."""
    row = store.conn.execute(
        "SELECT id, started_at, header_total, "
        "  (SELECT COUNT(DISTINCT COALESCE(item_key, icon_hash)) FROM observation "
        "    WHERE scan_id = scan.id) AS found "
        "FROM scan WHERE tab_label = ? ORDER BY id DESC LIMIT 1", (WEAPON_TAB,)
    ).fetchone()
    if row is None or not row["found"]:
        return None
    # Scans taken before D61 read the level as the count and saw no portraits:
    # they hold nothing this page can show, and say so rather than showing "0".
    weapons = store.conn.execute(
        "SELECT COUNT(DISTINCT COALESCE(item_key, icon_hash)) FROM observation "
        "WHERE scan_id = ? AND level IS NOT NULL", (row["id"],)
    ).fetchone()[0]
    return {
        "scan_id": row["id"], "scanned_at": row["started_at"],
        "found": row["found"], "total": row["header_total"], "weapons": weapons,
        "complete": row["header_total"] is not None and row["found"] == row["header_total"],
    }


def _who(name: str | None) -> str | None:
    """A holder's name as the rest of the app spells it. The game's panel says
    "漂泊者：气动装配中", but the 漂泊者 is ONE holder whatever the element (D72),
    and under any other spelling nothing finds their face or their weapon (D103)."""
    return ROVER if name and name.startswith(ROVER) else name


def copies(store: Store) -> list[Copy]:
    """Every tile of the newest 武器 scan, holders named where the user has named them."""
    scan = latest_scan(store)
    if scan is None:
        return []
    names = store.holder_names()
    out = []
    for row in store.conn.execute(
        """SELECT COALESCE(item_key, icon_hash) AS key, MAX(item_name) AS name,
                  MAX(level) AS level, MAX(holder_key) AS holder_key,
                  (SELECT o2.count FROM observation o2
                    WHERE o2.scan_id = o.scan_id
                      AND COALESCE(o2.item_key, o2.icon_hash) = COALESCE(o.item_key, o.icon_hash)
                      AND o2.count IS NOT NULL
                    ORDER BY o2.count_conf DESC LIMIT 1) AS count
             FROM observation o WHERE o.scan_id = ?
         GROUP BY COALESCE(o.item_key, o.icon_hash)""", (scan["scan_id"],)
    ):
        if row["level"] is None:
            continue  # a bag tile in the weapon tab: the weapon EXP materials
        out.append(Copy(
            key=row["key"], name=row["name"], level=row["level"],
            rank=min(max(row["count"] or 1, 1), MAX_RANK), holder_key=row["holder_key"],
            holder=_who(names.get(row["holder_key"])) if row["holder_key"] else None,
        ))
    return sorted(out, key=lambda c: (-(c.level or 0), -c.rank, c.name or "~"))


def summary(found: list[Copy]) -> dict:
    """What a weapon's copies add up to, under names of their own: `copies` on a
    weapon row is the PULL history (D53), and these two must not be confused.

    Merging counts in COPIES, not in weapons (D82). A copy at 谐振 r is r pulled
    copies rolled into one, and every merge is +1 regardless of what is fed in,
    so the pile is worth `sum(ranks)` copies however they are arranged: that many
    copies make `total // 5` weapons at 精5 with a `total % 5` one left over.

    不归孤军 -- 精4 and six 精1 -- is ten copies, so it is TWO 精5, not "one 精5
    with five wasted". 悖论喷流 (5/5/1/1/1/1) is fourteen: two 精5 and a 精4.
    """
    ranks = sorted((c.rank for c in found), reverse=True)
    total = sum(ranks)
    maxed = [r for r in ranks if r >= MAX_RANK]
    return {
        "owned_now": len(found),
        "rank_now": max(ranks, default=0),
        "rank_merged": reachable_rank(ranks),
        "total_rank": total,
        #: How many 精5 this pile makes, and what is left over after them.
        "fives": total // MAX_RANK,
        "rest_rank": total % MAX_RANK,
        "maxed_copies": len(maxed),
        "spare_copies": len(ranks) - len(maxed),
        "holders": [c.holder for c in found if c.holder],
    }


def owned_counts(store: Store, pulled: dict[str, int] | None = None) -> tuple[dict[str, int], bool]:
    """weapon -> how many the user has, and whether the bag is the whole truth.

    THE answer to "how many of this do I own", for every page (D103): with a
    complete 武器 scan it is the bag and nothing else -- a weapon the scan did not
    see is gone, whatever was once pulled (D82). Without one, the bag where it was
    seen and the pull history elsewhere, which is all there is.
    """
    scan = latest_scan(store)
    complete = bool(scan and scan["complete"] and scan["weapons"])
    have = {name: len(found) for name, found in by_weapon(store).items()}
    return (have if complete else {**(pulled or {}), **have}), complete


def by_weapon(store: Store) -> dict[str, list[Copy]]:
    out: dict[str, list[Copy]] = {}
    for copy in copies(store):
        if copy.name:
            out.setdefault(copy.name, []).append(copy)
    return out


def unknown(store: Store) -> list[dict]:
    """Weapon tiles nobody has named (D65).

    A weapon the catalogue has no artwork for cannot be recognised at all, so the
    武器 page shows the tile itself and asks. Naming it teaches the gallery.
    """
    scan = latest_scan(store)
    if scan is None:
        return []
    out = []
    for copy in copies(store):
        if copy.name:
            continue
        crops = store.item_crops(scan["scan_id"], copy.key)
        out.append({
            "key": copy.key, "scan_id": scan["scan_id"], "level": copy.level,
            "rank": copy.rank, "holder": copy.holder,
            "icon_key": crops[0] if crops else None,
        })
    return out


def held(store: Store) -> dict[str, Copy]:
    """resonator -> the copy they are carrying, as far as the scan can tell."""
    return {copy.holder: copy for copy in copies(store) if copy.holder and copy.name}


def holders(store: Store) -> dict[str, str]:
    """resonator -> the name of the weapon they are carrying."""
    return {who: copy.name for who, copy in held(store).items()}


def faces(store: Store, catalogue=None) -> list[dict]:  # noqa: ANN001 -- Catalogue
    """Every portrait seen on a weapon, with the weapons it was on (D61).

    The 武器 page asks about the unnamed ones; naming one names every weapon that
    face is holding, now and in later scans. With a catalogue, each face also
    carries the weapon TYPES it was seen on: only a resonator who uses that type
    can be the one carrying it, which cuts the picker from 64 faces to a dozen.
    """
    types = (catalogue.builds.get("weapons", {}) if catalogue is not None else {})
    learned = store.weapon_kinds()  # from the weapon's own panel, where the wiki is silent
    shortlist = {
        r["key"]: [n for n in (r["suggestions"] or "").split("|") if n]
        for r in store.holder_faces()
    }
    seen: dict[str, dict] = {}
    for copy in copies(store):
        if copy.holder_key is None:
            continue
        face = seen.setdefault(copy.holder_key, {
            "key": copy.holder_key, "name": copy.holder, "weapons": [], "types": [],
            "suggestions": shortlist.get(copy.holder_key, []), "held": [],
        })
        if copy.name and copy.name not in face["weapons"]:
            face["weapons"].append(copy.name)
            kind = (types.get(copy.name) or {}).get("type") or learned.get(copy.name)
            if kind and kind not in face["types"]:
                face["types"].append(kind)
            # The weapon as a picture: found on the page faster than its name is read.
            face["held"].append({
                "name": copy.name, "type": kind, "icon_key": copy.key,
                "icon_file": catalogue.icon_file(copy.name) if catalogue is not None else None,
            })
    return sorted(seen.values(), key=lambda f: (f["name"] is not None, f["key"]))
