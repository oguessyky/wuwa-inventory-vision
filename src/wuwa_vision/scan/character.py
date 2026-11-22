# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Where a resonator's screens, as read (D270), go.

The 属性详情 screen names the resonator; 技能 and 武器 do not, so they are the last 属性详情's
resonator's -- the game opens them from that resonator's page. An echo's panel names who holds
it. Every reading is kept per resonator (`Store.character_reads`), and the level and skill levels
also fill that resonator's progress (D57): the scan is a way in besides typing. The stat nodes
and a chain set by hand are left alone.
"""

from __future__ import annotations

import json

import numpy as np

from ..ocr import character
from ..store.db import Store
from .portraits import ROVER, Column, Portraits, column, plain, same_selection


class CharacterReader:
    def __init__(self, store: Store) -> None:
        self.store = store
        self.current: str | None = None

    def told(self, who: str | None) -> None:
        """The portraits on the right said whose screen this is (D341): a name, or None for
        someone never learned. Their screens are kept under them, not the last 属性详情's."""
        self.current = who

    def take(self, reading: dict) -> str | None:
        """Keep one screen's reading; the resonator it was kept under, or None."""
        kind = reading.get("kind")
        if kind == "attributes":
            self.current = reading.get("name")
            if not self.current:
                return None
            self.store.save_character_read(self.current, "attributes", reading)
            self._progress(reading)
            return self.current
        if kind in ("skills", "weapon"):
            if not self.current:
                return None
            self.store.save_character_read(self.current, kind, reading)
            if kind == "skills":
                self._progress(reading)
            return self.current
        if kind == "echo":
            holder = reading.get("holder")
            if not holder or not reading.get("name"):
                return None
            # what an earlier read of this piece had and this one missed is kept (D359):
            # 辛吉勒姆's "COST 4" read once, "COST.4" (none) the next time
            before = self.store.character_read(holder, "echo", reading["name"]) or {}
            for field in ("level", "cost", "set"):
                if reading.get(field) is None and before.get(field) is not None:
                    reading[field] = before[field]
            self.store.save_character_read(holder, "echo", reading, key=reading["name"])
            return holder
        if kind == "chain":
            # nothing is read from 共鸣链, nor kept: whose it is names the card (D359)
            return self.current
        if kind == "echoes":
            # the 声骸 page: what they wear (D340), the last 属性详情's resonator's. Kept as
            # `worn`: `echoes` in character_reads is the list of single echoes read
            if not self.current or not reading.get("sets"):
                return None
            self.store.save_character_read(self.current, "worn", reading)
            return self.current
        return None

    def _progress(self, reading: dict) -> None:
        """Into their progress, read just now (D57, D270): the same as a home does with it
        (D342)."""
        if self.current:
            with self.store.conn:
                self.store.progress_from_read(self.current, reading)


def _lists() -> dict:
    """The names a reading snaps onto: 计算's data (D268) when it is fetched, else the
    catalogue's resonators and weapons."""
    from ..calc_data import cached
    from ..catalogue import CATALOGUE_DIR, Catalogue

    data = cached(CATALOGUE_DIR)
    if data:
        return {
            "names": {n: r.get("element") for n, r in data["roles"].items()},
            "echoes": list(data.get("echoes") or {}),
            "sets": list(data.get("sets") or {}),
            "weapons": list(data.get("weapons") or {}),
        }
    catalogue = Catalogue.load()
    return {
        "names": {n: None for n in catalogue.builds.get("resonators") or {}},
        "echoes": [],
        "sets": [],
        "weapons": list(catalogue.builds.get("weapons") or {}),
    }


#: The echo panel, as the window's height from its right edge (ocr/character.py), and how
#: different its small picture must be to be another echo.
_PANEL = (0.64, 0.1, 0.0, 0.7)
_CHANGED = 6.0


#: A stat's word on these screens, by 计算's key (the reverse of `ocr.character.LABELS`).
_WORDS = {key: word for word, key in character.LABELS.items()}
#: Stats that are an amount, not a share.
_FLAT = {"hp", "atk", "def"}


def stat_words(stat: str, value: object) -> str:
    """A stat as the game says it (D343): 生命 34628, 暴击 20.0%, 生命 30.3% for a share of HP."""
    share = stat.endswith("_pct") or stat not in _FLAT
    word = _WORDS.get(stat.removesuffix("_pct"), stat)
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return f"{word} {value}"
    return f"{word} {number * 100:.1f}%" if share else f"{word} {round(number)}"


def summary(said: dict) -> list[str]:
    """Everything a screen's reading says, line by line in the game's words, for the scan's
    pages (D340, D343): so a read can be seen, whose and every value, not only a log line."""
    kind = said.get("kind")
    lv = f"Lv {said.get('level')}/{said.get('cap')}" if said.get("level") else None
    if kind == "attributes":
        element = next((w for w, n in character.ELEMENTS.items() if n == said.get("element")),
                       None)
        head = [x for x in (said.get("name"), element, lv) if x]
        return head + [stat_words(k, v) for k, v in (said.get("stats") or {}).items()]
    if kind == "skills":
        nodes = said.get("nodes") or {}
        stat = [n for k, v in nodes.items() if k != "共鸣回路" for n in v]
        inherent = nodes.get("共鸣回路") or []
        told = [f"属性节点 {sum(n is True for n in stat)}/{len(stat)}"] if stat else []
        if inherent:
            told.append(f"固有技能 {sum(n is True for n in inherent)}/{len(inherent)}")
        return [f"{k} {v}" for k, v in (said.get("skills") or {}).items()] + told
    if kind == "weapon":
        rank = f"谐振 {said.get('rank')}" if said.get("rank") else None
        head = [x for x in (said.get("name"), lv, rank) if x]
        return head + [stat_words(k, v) for k, v in (said.get("stats") or {}).items()]
    if kind == "echo":
        head = [x for x in (said.get("name"), said.get("set"),
                            f"Lv {said.get('level')}" if said.get("level") is not None else None,
                            f"COST {said.get('cost')}" if said.get("cost") else None,
                            f"{said.get('holder')} 装配中" if said.get("holder") else None) if x]
        main = [f"主 {stat_words(s['stat'], s['value'])}" for s in said.get("main") or []]
        subs = [f"副 {stat_words(s['stat'], s['value'])}" for s in said.get("subs") or []]
        return head + main + subs
    if kind == "echoes":
        worn = [f"{s['name']} {s['pieces']}/{s['of']}" for s in said.get("sets") or []]
        totals = [f"{k} {v}" for k, v in (said.get("stats") or {}).items()]
        return worn + totals
    return []


#: The screens kept per resonator, as `holds_of` lists them.
_KEPT = ("attributes", "weapon", "skills", "worn")


def holds_of(store: Store, name: str) -> list[dict]:
    """Everything the scan holds for a resonator (D343), screen by screen, each in the game's
    words: what the scan's pages list in place of the bag's items on that resonator's screens."""
    out = []
    rows = store.conn.execute(
        "SELECT screen, key, data, read_at FROM character_reads WHERE resonator = ? "
        "ORDER BY read_at DESC", (name,)
    ).fetchall()
    if name.startswith(f"{ROVER}·"):
        # every element of the 漂泊者 holds the one weapon (D370)
        shared = store.rover_weapon_read()
        rows = [r for r in rows if r["screen"] != "weapon"] + ([shared] if shared else [])
    for row in rows:
        data = json.loads(row["data"])
        kind = "echoes" if row["screen"] == "worn" else row["screen"]
        out.append({"kind": kind, "key": row["key"], "summary": summary({**data, "kind": kind}),
                    "data": {**data, "kind": kind}, "read_at": row["read_at"]})
    order = {k: i for i, k in enumerate(_KEPT)}
    return sorted(out, key=lambda h: (order.get(h["kind"], len(order)), h["key"]))


def pictures() -> dict[str, dict[str, str]]:
    """The catalogue's pictures by name (D357): the resonators' head icons, the echoes' and the
    sets' art -- what the scan's page lays a resonator's screens out with. Files only; the
    monitor serves them. Nothing when the catalogue has none."""
    import json as _json

    from ..catalogue import CATALOGUE_DIR, Catalogue

    try:
        drawn = _json.loads((CATALOGUE_DIR / "echoes.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        drawn = {}
    try:
        avatars = dict(Catalogue.load().avatars.get("resonators") or {})
    except Exception:  # noqa: BLE001 -- no catalogue yet: the page draws without pictures
        avatars = {}
    try:
        from ..recognize.reference import name_to_file

        weapons = dict(name_to_file())  # a weapon's picture, as the main app draws it (D365)
    except Exception:  # noqa: BLE001 -- no catalogue yet: the page draws without pictures
        weapons = {}
    return {"avatars": avatars, "echoes": dict(drawn.get("echoes") or {}),
            "sets": dict(drawn.get("sets") or {}), "weapons": weapons}


def dress(entry: dict, pics: dict) -> dict:
    """`entry` (a screen read, or one held) with the pictures of what it names (D357): `icons`,
    each echo's and set's by name, an echo's other form (异相·) drawn as the echo it is a form of
    as 计算 draws it (D269); and `avatar`, the resonator's head icon."""
    echoes, sets, avatars = pics.get("echoes") or {}, pics.get("sets") or {}, \
        pics.get("avatars") or {}
    data = entry.get("data") or {}
    icons: dict[str, str] = {}

    def echo(name: str | None) -> None:
        file = echoes.get(name or "") or echoes.get((name or "").removeprefix("异相·"))
        if name and file:
            icons[name] = f"api/echo/{file}"

    def a_set(name: str | None) -> None:
        if name and sets.get(name):
            icons[name] = f"api/echo/{sets[name]}"

    if data.get("kind") == "echo":
        echo(data.get("name"))
        a_set(data.get("set"))
    if data.get("kind") == "weapon" and (pics.get("weapons") or {}).get(data.get("name") or ""):
        icons[data["name"]] = f"api/reference/{pics['weapons'][data['name']]}"
    for worn in data.get("sets") or []:
        a_set(worn.get("name"))
    who = entry.get("resonator") or (data.get("name") if data.get("kind") == "attributes"
                                     else None)
    avatar = avatars.get(who or "")
    if avatar is None and (who or "").startswith("漂泊者"):
        avatar = avatars.get("女漂泊者" if "女" in who else "男漂泊者")
    return {**entry, "icons": icons, "avatar": f"api/avatar/{avatar}" if avatar else None}


def _thumb(rgb: np.ndarray) -> np.ndarray:
    h, w = rgb.shape[:2]
    left, top, right, bottom = _PANEL
    crop = rgb[int(top * h) : int(bottom * h), w - int(left * h) : w - int(right * h)]
    step = max(1, crop.shape[0] // 48)
    return crop[::step, ::step].astype(np.float32).mean(axis=2)


#: The screens a read is held on while whose cannot be told (D370); 共鸣链 keeps nothing.
_HOLD = ("skills", "weapon", "echoes")


class CharacterScreens:
    """A live scan's eye for a resonator's own screens (D270): `look` reads a still frame that is
    one of them and keeps what it says; `panel_changed` tells a click on another echo in the bag,
    which changes too little of the window for the frame gate."""

    def __init__(self, store: Store, lists: dict | None = None) -> None:
        self.reader = CharacterReader(store)
        self.portraits = Portraits(store)
        self.lists = lists if lists is not None else _lists()
        self.last_kind: str | None = None
        self._panel: np.ndarray | None = None
        #: the last reading taken, with whose it was, and whose it was kept as (D359)
        self._last: str | None = None
        self._last_who: str | None = None
        #: the last screen whose resonator was known, and the column of portraits it showed
        #: (D370): a screen after it with the same portrait selected is theirs
        self._anchor: tuple[str, Column | None] | None = None
        #: reads held while whose cannot be told, by screen, the column they showed, and why:
        #: "unsure" (the portraits cannot say) or "rover" (the 漂泊者, element not known)
        self._held: dict[str, dict] = {}
        self._held_col: Column | None = None
        self._held_why: str | None = None

    def look(self, rgb: np.ndarray, kind: str | None = None) -> dict | None:
        """`kind`: which screen this is, when the scan knows it already (D331)."""
        said, lines = character.read_with_boxes(rgb, kind=kind, **self.lists)
        if said is None or (said["kind"] != "chain" and not summary(said)):
            # nothing read: a page caught as it changed is no read, and leaves whose screen it
            # is as it was (D359)
            self.last_kind = None
            return None
        self.last_kind = said["kind"]
        who: str | None = None
        why: str | None = None     # whose is asked (D370): not kept, the scan's page says why
        col: Column | None = None
        sure = False               # whose said by a portrait surely someone's, known
        if said["kind"] == "echo":
            self._panel = _thumb(rgb)
            holder = said.get("holder")
            if holder and plain(holder) == ROVER:
                # the panel says 漂泊者, not which: the 漂泊者 on screen's form (D370)
                now = self.reader.current or ""
                if now.startswith(f"{ROVER}·"):
                    said = {**said, "holder": now}
                else:
                    why = "rover"
            who = said.get("holder")
        elif said["kind"] == "attributes":
            who = said.get("name")
            if who == ROVER:
                # a 漂泊者 with the element not read: which form is not known (D370)
                who, why = None, "rover-element"
            elif who:
                col = column(rgb)
                # their name is read here: so is their portrait on the right (D341)
                self.portraits.learn(rgb, who)
        else:
            col = column(rgb)
            who, why, sure = self._whose(rgb, col)
            if said["kind"] == "chain" and why:
                # nothing is read from 共鸣链, nor kept (D359): nothing to hold, nothing asked
                why = None
        # held still, a page is read again and again (D359): the same reading of the same
        # resonator's screen is no news, neither said nor kept again
        same = json.dumps([said, who, why], ensure_ascii=False, sort_keys=True)
        if same == self._last:
            return {"kind": said["kind"], "resonator": self._last_who, "same": True,
                    "summary": summary(said), "data": said}
        self._last = same
        out: dict = {"kind": said["kind"], "summary": summary(said), "data": said}
        if why:
            held = said["kind"] in _HOLD
            if held:
                self._hold(said, col, why)
            self._last_who = None
            out.update(resonator=None, ask={"why": why, "held": list(self._held) if held else []})
        else:
            if said["kind"] == "attributes" or (sure and who):
                settled = self._settle(who, col, by_name=said["kind"] == "attributes")
                if settled is not None:
                    out["settled"] = settled
            if said["kind"] not in ("attributes", "echo"):
                self.reader.told(who)
            if who and said["kind"] != "echo":
                self._anchor = (who, col)
            self._last_who = self.reader.take(said)
            out["resonator"] = self._last_who
        h, w = rgb.shape[:2]
        # every value read, and where each piece of text was: the scan's pages draw them (D343)
        return {**out, "frame": [w, h],
                "boxes": [[round(x.x0, 4), round(x.y0, 4), round(x.x1, 4), round(x.y1, 4), x.text]
                          for x in lines if x.text]}

    def _whose(self, rgb: np.ndarray, col: Column | None) -> tuple[str | None, str | None, bool]:
        """技能, 武器, the 声骸 page, 共鸣链: whose, by the portrait selected on the right (D341),
        else asked (D370): (whose, why asked, whether a portrait surely said so)."""
        told, who = self.portraits.look(rgb)
        anchor, anchor_col = self._anchor or (None, None)
        if told and who is not None:
            if plain(who) != ROVER:
                return who, None, True
            # the 漂泊者: which form only 属性详情 says; theirs while they stay on screen
            if anchor and anchor.startswith(f"{ROVER}·"):
                return anchor, None, True
            return None, "rover", False
        if col is None:
            # no portraits on screen, none to pick another with: the last one told
            return self.reader.current, None, False
        # unsure, or a portrait never learned: theirs, if the same portrait is still selected
        if anchor is not None and anchor_col is not None and same_selection(anchor_col, col):
            if told and col.selected.sure:
                # surely selected, never learned: it is theirs (their 属性详情's pick was unsure)
                self.portraits.keep(anchor, col.pictures[col.selected.slot - 1])
            return anchor, None, False
        return None, "unsure", False

    def _hold(self, said: dict, col: Column | None, why: str) -> None:
        """Hold a read until whose is told (D370); another portrait selected starts again."""
        if self._held and (why != self._held_why or not (
                col is None or self._held_col is None or same_selection(self._held_col, col))):
            self._held = {}
        self._held[said["kind"]] = said
        self._held_col, self._held_why = col, why

    def _settle(self, name: str, col: Column | None, by_name: bool) -> dict | None:
        """What was held, now that whose is told: kept under `name` when the same portrait is
        selected, else dropped. Told by 属性详情 (`by_name`), which settles it either way, or by
        a portrait surely someone's, which keeps it or leaves it held. None: nothing settled."""
        if not self._held:
            return None
        if self._held_why == "rover":
            ok = name.startswith(f"{ROVER}·") and (
                col is None or self._held_col is None or same_selection(self._held_col, col))
        else:
            ok = col is not None and self._held_col is not None and same_selection(
                self._held_col, col)
        if not ok and not by_name:
            return None
        held, self._held, self._held_col, self._held_why = self._held, {}, None, None
        if ok:
            for said in held.values():
                self.reader.told(name)
                self.reader.take(said)
        return {"to": name, "kept": list(held) if ok else [], "dropped": [] if ok else list(held)}

    def panel_changed(self, rgb: np.ndarray) -> bool:
        if self.last_kind != "echo" or self._panel is None:
            return False
        now = _thumb(rgb)
        if now.shape != self._panel.shape:
            return True
        return float(np.abs(now - self._panel).mean()) > _CHANGED
