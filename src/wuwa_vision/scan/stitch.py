# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Cross-frame stitching: many overlapping views -> one inventory.

A scan sees the bag through a sliding window, and consecutive frames overlap by
however far the user scrolled. Stitching de-duplicates those overlaps and keeps
the best reading of each item.

Identity is **grid position**, not icon content hash. The hash was sound on
fixtures -- a shifted fixture reproduces its crops bit-for-bit -- but a live
capture never does: box jitter and resampling during scroll gave a real 8-frame
scan 185 distinct hashes for roughly 68 distinct items, which then passed the
header check (185 >= 170) and stopped the scan as "complete" at ~40% coverage.

So each frame is *registered* against what is already known. Tiles are compared
by a small appearance vector within the same column (scrolling is vertical, so a
column never changes) and each good match votes for a vertical offset; the
winning offset places every tile of the frame in one bag-wide coordinate system,
and a tile landing on an occupied slot is that item again. A frame with no
overlap cannot be placed safely: it is still stitched, but flagged as a gap so
the user is told to scroll back.

Counts are merged by **confidence, not recency**. The same item seen twice can be
read once cleanly and once during a badge animation; taking the later read would
throw away the better one.

Completion is decided by the game's own header count (`资源 111/1000`). Finding
MORE items than the header is not completion but a stitching failure, and is
reported as such (PLAN.md D8/D15).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..store.db import Observation

#: Appearance similarity for a same-column match to vote for a scroll offset.
#: Measured on a live scan: re-sightings of one item score 0.995+, and distinct
#: items plateau at ~68 clusters anywhere between 0.95 and 0.97.
VOTE_SIMILARITY = 0.95
#: Stricter bar for merging by appearance alone, when a frame could not be placed.
APPEARANCE_ONLY_SIMILARITY = 0.98
#: Votes needed before an offset is trusted.
MIN_VOTES = 2
#: Contour box height -> row pitch, used only until two rows reveal the real pitch.
PITCH_PER_BOX_HEIGHT = 1.16


@dataclass
class StitchedItem:
    """One distinct item, merged across every frame it appeared in."""

    icon_hash: str
    rarity: int
    count: int | None = None
    count_confidence: float = 0.0
    item_name: str | None = None
    sightings: int = 0
    x: float | None = None
    """Tile centre x in frame pixels. Horizontal position never scrolls."""
    y: float | None = None
    """Tile top in bag coordinates (frame y + that frame's registered offset)."""
    descriptor: np.ndarray | None = field(default=None, repr=False)
    confirmed: bool = False
    """Name and count were read from the detail panel for this very item."""
    rivals: tuple[str, ...] = ()
    """Looks identical to all these named items; the user must click it (D31)."""
    level: int | None = None
    """武器 tiles: the weapon's level (D61). One copy per tile, so per-tile."""
    holder_key: str | None = None
    """武器 tiles: the portrait of whoever has it equipped (D61)."""

    @property
    def needs_click(self) -> bool:
        return not self.confirmed and len(self.rivals) >= 2

    @property
    def needs_review(self) -> bool:
        if self.confirmed:
            return False
        return self.count is None or self.count_confidence < 0.70

    def confirm(self, name: str | None, owned: int | None) -> None:
        """Adopt the detail panel's reading. It outranks tile OCR and the gallery."""
        if name:
            self.item_name = name
        if owned is not None:
            self.count = owned
            self.count_confidence = 1.0
        self.confirmed = True


@dataclass
class Stitcher:
    """Accumulates observations across frames into distinct items."""

    items: dict[str, StitchedItem] = field(default_factory=dict)
    frames: int = 0
    total_observations: int = 0
    header_total: int | None = None
    pitch: float | None = None
    """Row pitch in pixels, learned from the frames."""
    gaps: int = 0
    """Frames that shared nothing with what was already seen (scrolled too far)."""
    last_new: list[StitchedItem] = field(default_factory=list)
    """Items first seen in the most recent frame."""
    last_registered: bool = True
    """False when the most recent frame could not be placed against earlier ones."""
    obs_keys: list[str] = field(default_factory=list)
    """Item key per observation of the most recent frame, aligned with its input."""
    misplaced: int = 0
    """Frames whose offset put a tile on a slot it provably is not (D92)."""
    _trust_slots: bool = True

    def add_frame(self, observations: list[Observation]) -> int:
        """Merge one frame's observations. Returns how many items were new."""
        self.frames += 1
        self.last_new = []
        self.obs_keys = []
        placed = [o for o in observations if o.box is not None and o.descriptor is not None]
        self._learn_pitch(placed)

        # The slot decides only while nothing contradicts it. On the 武器 tab,
        # rows of identical copies can win the offset vote one row off, and then
        # every tile inherits the item on the slot it landed on: a 精5 Lv.60
        # spear with a holder and a 精1 Lv.1 blade became one "item", the blade's
        # crops took the spear's name, and the gallery poisoned itself (D92).
        #
        # So an offset is a candidate until nothing contradicts it, and the next
        # best-supported one is tried when something does. A frame no candidate
        # fits has not been placed at all: after a full page of scroll the copies
        # voted for a spot 2500 px up, the frame's 27 new weapons were stored
        # THERE, and the next view of the same tiles collided with what already
        # lived at that spot -- one clicked weapon became two (D96).
        self._trust_slots = True
        offset = None
        for rank, candidate in enumerate(self._offsets(placed)):
            if not self._contradicted(observations, candidate):
                offset = candidate
                break
            if rank == 0:
                self.misplaced += 1
        self.last_registered = offset is not None or not self._positioned()
        self._trust_slots = self.last_registered
        if offset is None:
            if self._positioned() and placed:
                self.gaps += 1
                # Assume the user scrolled on past everything known. Only the
                # appearance-only merge in _find protects against that guess.
                bottom = max(i.y for i in self.items.values() if i.y is not None)
                offset = bottom + (self.pitch or 0.0) - min(o.box[1] for o in placed)
            else:
                offset = 0.0

        claimed: set[str] = set()
        for obs in observations:
            self.total_observations += 1
            item = self._find(obs, offset, claimed)
            if item is None:
                item = StitchedItem(
                    icon_hash=obs.icon_hash,
                    rarity=obs.rarity,
                    count=obs.count,
                    count_confidence=obs.count_conf,
                    item_name=obs.item_name,
                    sightings=1,
                    x=_centre_x(obs),
                    y=(obs.box[1] + offset) if obs.box is not None else None,
                    descriptor=obs.descriptor,
                    rivals=obs.rivals,
                    level=obs.level,
                    holder_key=obs.holder_key,
                )
                self.items[obs.icon_hash] = item
                self.last_new.append(item)
                if obs.from_panel:
                    item.confirm(obs.item_name, obs.count)
            elif obs.from_panel:
                item.sightings += 1
                item.confirm(obs.item_name, obs.count)
            else:
                item.sightings += 1
                # Keep the most confident count, not the most recent one. A
                # panel-confirmed count is final.
                if (
                    not item.confirmed
                    and obs.count is not None
                    and obs.count_conf > item.count_confidence
                ):
                    item.count = obs.count
                    item.count_confidence = obs.count_conf
                # A name, once known, is never downgraded to unknown.
                if item.item_name is None and obs.item_name is not None:
                    item.item_name = obs.item_name
                if obs.rivals and not item.confirmed:
                    item.rivals = obs.rivals
                # A click view reads neither, so absence is "not looked at"
                # rather than "not there" -- never unset what a full view saw.
                if obs.level is not None:
                    item.level = obs.level
                if obs.holder_key is not None:
                    item.holder_key = obs.holder_key
            claimed.add(item.icon_hash)
            self.obs_keys.append(item.icon_hash)
        return len(self.last_new)

    # ------------------------------------------------------------ placement

    def _contradicted(self, observations: list[Observation], offset: float) -> bool:
        """Would placing this frame at `offset` put any tile on an item it is not?"""
        claimed: set[str] = set()
        for obs in observations:
            item = self._find(obs, offset, claimed)
            if item is None:
                continue
            if _contradicts(obs, item):
                return True
            claimed.add(item.icon_hash)
        return False

    def _positioned(self) -> bool:
        return any(i.y is not None for i in self.items.values())

    def _learn_pitch(self, placed: list[Observation]) -> None:
        if not placed:
            return
        heights = [o.box[3] - o.box[1] for o in placed]
        tol = 0.3 * float(np.median(heights))
        rows: list[float] = []
        for top in sorted(o.box[1] for o in placed):
            if not rows or top - rows[-1] > tol:
                rows.append(top)
        if len(rows) >= 2:
            self.pitch = float(np.median(np.diff(rows)))
        elif self.pitch is None:
            self.pitch = float(np.median(heights)) * PITCH_PER_BOX_HEIGHT

    @staticmethod
    def _same_column(obs: Observation, item: StitchedItem) -> bool:
        width = obs.box[2] - obs.box[0]
        return item.x is not None and abs(item.x - _centre_x(obs)) < width / 2

    def _register(self, placed: list[Observation]) -> float | None:
        """The vertical offset that maps this frame onto bag coordinates, if any."""
        offsets = self._offsets(placed)
        return offsets[0] if offsets else None

    def _offsets(self, placed: list[Observation]) -> list[float]:
        """Every offset enough tiles vote for, best supported first."""
        known = [i for i in self.items.values() if i.y is not None and i.descriptor is not None]
        if not known or not placed:
            return []
        votes: list[float] = []
        for obs in placed:
            for item in known:
                if item.rarity != obs.rarity or not self._same_column(obs, item):
                    continue
                if float(item.descriptor @ obs.descriptor) >= VOTE_SIMILARITY:
                    votes.append(item.y - obs.box[1])
        tol = 0.25 * (self.pitch or 1.0)
        needed = min(MIN_VOTES, len(placed))
        offsets: list[float] = []
        while votes:
            best = max(votes, key=lambda v: sum(abs(v - u) <= tol for u in votes))
            support = [u for u in votes if abs(best - u) <= tol]
            if len(support) < needed:
                break
            offsets.append(float(np.median(support)))
            votes = [u for u in votes if abs(best - u) > tol]
        return offsets

    def _find(self, obs: Observation, offset: float, claimed: set[str]) -> StitchedItem | None:
        """The already-known item this observation is, or None if it is new."""
        exact = self.items.get(obs.icon_hash)
        if exact is not None and exact.icon_hash not in claimed:
            return exact
        if obs.box is None or obs.descriptor is None:
            return None

        y = obs.box[1] + offset
        half = 0.5 * (self.pitch or (obs.box[3] - obs.box[1]))
        candidates = [
            i for i in self.items.values()
            if i.icon_hash not in claimed and i.y is not None and self._same_column(obs, i)
        ]
        if self._trust_slots:
            # Placed: the slot decides. The grid is the game's own ordering, so a
            # tile on an occupied slot is that item whatever its crop looks like --
            # unless a fact that cannot change mid-scan says otherwise (D92).
            for item in candidates:
                if abs(item.y - y) < half:
                    return item
            return None
        # Not placed: only a near-identical crop in the same column counts.
        scored = [
            (float(i.descriptor @ obs.descriptor), i)
            for i in candidates
            if i.descriptor is not None and i.rarity == obs.rarity and not _contradicts(obs, i)
        ]
        if scored:
            score, item = max(scored, key=lambda t: t[0])
            if score >= APPEARANCE_ONLY_SIMILARITY:
                return item
        return None

    # -------------------------------------------------------------- summary

    @property
    def unique(self) -> int:
        return len(self.items)

    @property
    def named(self) -> int:
        return sum(1 for i in self.items.values() if i.item_name)

    @property
    def needs_review(self) -> int:
        return sum(1 for i in self.items.values() if i.needs_review)

    @property
    def duplicate_rate(self) -> float:
        """Fraction of observations that were re-sightings. 0.0 when nothing overlapped."""
        if not self.total_observations:
            return 0.0
        return 1.0 - (self.unique / self.total_observations)

    @property
    def complete(self) -> bool:
        """True only when the game's own count agrees with what we found.

        Equality, not >=: finding more items than the game has means stitching
        split one item into several, and must never read as done.
        """
        return self.header_total is not None and self.unique == self.header_total

    @property
    def overcount(self) -> int:
        """Items beyond the header count. Non-zero means stitching went wrong."""
        if self.header_total is None:
            return 0
        return max(self.unique - self.header_total, 0)

    @property
    def remaining(self) -> int | None:
        if self.header_total is None:
            return None
        return max(self.header_total - self.unique, 0)

    def progress(self) -> str:
        if self.header_total is None:
            return f"{self.unique} items (header count unknown)"
        text = f"{self.unique}/{self.header_total} items"
        if self.overcount:
            text += f"  (!{self.overcount} more than the game reports -- duplicates)"
        return text

    def sorted_items(self) -> list[StitchedItem]:
        """Bag order (top-to-bottom, left-to-right) where known."""
        return sorted(
            self.items.values(),
            key=lambda i: (
                i.y is None,
                round(i.y / self.pitch) if i.y is not None and self.pitch else 0,
                i.x or 0.0,
            ),
        )


def _contradicts(obs: Observation, item: StitchedItem) -> bool:
    """A fact that cannot change during a scan disagrees: not the same tile (D92).

    A weapon's level and its 谐振 rank are fixed while the bag is open. Each is
    compared only when BOTH sides were read -- a click view reads none of them
    for the tiles it did not click, and absence is not evidence.

    The holder is fixed too, but its key is not a fact: it is a likeness call on
    a small portrait, and a 1 px shift of the tile box gave one face two keys
    (0.93-0.97 against SAME_FACE 0.97). Holding that against the slot distrusted
    every frame and split each clicked weapon in two (D93).
    """
    if obs.level is None or item.level is None:
        return False  # not a weapon tile, or not read: nothing to hold against it
    if obs.level != item.level:
        return True
    return (obs.count is not None and item.count is not None and obs.count_conf >= 0.9
            and item.count_confidence >= 0.9 and obs.count != item.count)


def _centre_x(obs: Observation) -> float | None:
    return None if obs.box is None else (obs.box[0] + obs.box[2]) / 2
