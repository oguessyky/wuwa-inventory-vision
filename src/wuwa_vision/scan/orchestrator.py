# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Scan orchestration: frames in, persisted observations out.

One per-frame pipeline serves both paths. `run_scan` walks a finite sequence of
frames (fixtures, Milestone 1). `run_live_scan` drives the same pipeline from live
capture, adding what live scanning needs and replay does not: frame gating,
cross-frame stitching, one scan per bag tab, detail-panel reads, and a panic key.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

from ..capture.base import Frame
from ..catalogue import Catalogue
from ..ocr import currency as currency_mod
from ..ocr import header as header_mod
from ..ocr.engine import read_tile_count
from ..ocr.weapon import read_level
from ..pulls import resolve as resolve_pulls
from ..recognize.appearance import describe, hue_signature
from ..recognize.holders import HolderRead, Holders
from ..recognize.names import catalogue_names, snap, weapon_names, weapon_types
from ..recognize.selection import selected_index
from ..recognize.tiles import Tile, detect_tiles
from ..store.db import Observation, Store, icon_hash
from .stitch import Stitcher

if TYPE_CHECKING:  # importing the gallery pulls in torch; keep it off the M1 path
    from ..capture.gating import FrameGate
    from ..ocr.panel import Panel
    from ..recognize.gallery import Gallery, Match
    from ..safety.panic import PanicKey

#: Counts below this OCR confidence are flagged for hover fallback, never trusted.
MIN_COUNT_CONFIDENCE = 0.70
#: A frame yielding fewer tiles than this is almost certainly not the inventory.
MIN_TILES_PER_FRAME = 4
#: Panel reads below this confidence are not allowed to name or count anything.
MIN_PANEL_CONFIDENCE = 0.80
#: Tabs never scanned, matched as substrings of the header label:
#: 声骸 (echoes -- ~1400 entries, each unique, not inventory counts), 任务 (the
#: quest-items tab, the document-with-"!" rail icon) (D28), and 特殊 (special
#: items: gift boxes, selector chests) at the user's request (D41). 武器 was here
#: (D34) and is scanned again by default (D56): its views are the material for the
#: weapon reader (who holds which weapon); its tiles show a LEVEL, not a count, so
#: the main app's bag pages leave that tab out. Header misreads such as 器润 are
#: snapped to 武器 before this list is consulted (header.canonical_label, D35).
DEFAULT_SKIP_TABS: tuple[str, ...] = ("声骸", "任务", "特殊")


def is_skipped(label: str | None, skip_tabs: Iterable[str]) -> bool:
    return label is not None and any(s and s in label for s in skip_tabs)


@dataclass(slots=True)
class ScanReport:
    scan_id: int
    frames_used: int = 0
    frames_skipped: int = 0
    tiles: int = 0
    unique: int = 0
    header_total: int | None = None
    tab_label: str | None = None
    needs_review: int = 0
    """Tiles whose COUNT could not be read confidently."""
    unnamed: int = 0
    """Tiles the gallery could not name. Distinct from a bad count read."""
    identified: int = 0
    doubted: int = 0
    """5-star weapon names the pull history contradicts: left for a click (D101)."""
    gallery_added: int = 0
    panel_reads: int = 0
    """Items named and counted from the detail panel."""
    holders_named: int = 0
    """Portraits named by the panel's own "X装配中" (D64)."""
    last_panel: Panel | None = None
    panel_attempt: list[tuple[float, str, float]] | None = None
    """Raw OCR lines of this view's panel read, when one was attempted."""
    last_matches: list[object | None] = field(default_factory=list)
    """The gallery's answer per tile of the most recent view (None: not queried)."""
    """The panel read on the most recent view, when it was a new one."""
    panel_unmatched: Panel | None = None
    """A panel read this view that could not be matched to the selected tile."""
    aborted: bool = False
    """True when the panic key stopped the scan."""
    frames_unfocused: int = 0
    """Frames dropped because the game window was not in the foreground."""
    stop_reason: str = ""
    skipped_reasons: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        """True only when the game's own count agrees with what we found.

        Equality: more items than the game reports is a stitching failure.
        """
        return self.header_total is not None and self.unique == self.header_total


#: Selected-tile crops at least this alike (appearance.describe) are one item.
SAME_SELECTION = 0.97
#: A panel read that could not be attached is retried this many times for one
#: selection, then left until the user clicks something else.
MAX_PANEL_TRIES = 2
#: While the screen is still, look for a moved selection outline this often (s).
SELECTION_PROBE = 0.4


@dataclass
class SelectionMemo:
    """Which tile the last panel read was for, so one selection is OCR'd once.

    Keyed on the SELECTED TILE, not the panel's pixels: the panel shows animated
    item art, so a pixel check re-read it on every view (3-6 s each, D39).
    """

    look: np.ndarray | None = None
    box: tuple[int, int, int, int] | None = None
    tries: int = 0
    settled: bool = False
    """Attached, or given up after MAX_PANEL_TRIES."""

    def is_same(self, look: np.ndarray, box: tuple[int, int, int, int], scrolled: bool) -> bool:
        """Same selection as last time.

        Without a scroll, the place decides: the same tile is the same selection
        (its crop changes as the outline animates -- live, one tile scored below
        SAME_SELECTION and its panel was read twice), and a same-looking tile
        elsewhere is a twin. After a scroll the tile has moved, so its look decides.
        """
        if self.look is None or self.box is None:
            return False
        if scrolled:
            return float(self.look @ look) >= SAME_SELECTION
        width = box[2] - box[0]
        return abs(self.box[0] - box[0]) < width / 2 and abs(self.box[1] - box[1]) < width / 2

    def needs_read(self, look: np.ndarray, box: tuple[int, int, int, int], scrolled: bool) -> bool:
        if self.is_same(look, box, scrolled):
            self.box = box
            return not self.settled
        self.look, self.box, self.tries, self.settled = look, box, 0, False
        return True

    def ignore(self, rgb: np.ndarray, tiles: list[Tile], scrolled: bool) -> None:
        """Settle the visible selection without reading it (a skipped tab).

        Otherwise the click probe finds it unread every 0.4 s, forever.
        """
        chosen = selected_index(rgb, tiles)
        if chosen is not None:
            self.needs_read(describe(tiles[chosen].icon), tiles[chosen].box, scrolled)
            self.settled = True

    def result(self, attached: bool) -> None:
        self.tries += 1
        self.settled = attached or self.tries >= MAX_PANEL_TRIES


#: Largest per-cell change (0-255, on a 64x16 thumbnail of the header) that still
#: counts as "same header". MAX, not mean: the label is a small part of the strip,
#: and a real tab switch (素材 -> 补给) moved the MEAN by only 1.6 while its max was
#: 143. Within one tab, views differed by at most 8 (D29).
HEADER_CHANGE = 20.0


@dataclass
class HeaderMemo:
    """Re-reads the header only when its pixels change.

    The header (`补给 170/1000`) is constant while scrolling a tab, yet OCR'ing it
    cost ~1.7 s of every view on CPU. It changes on a tab switch or when an item
    runs out -- both change the pixels, so a pixel check loses nothing.
    """

    signature: np.ndarray | None = None
    header: header_mod.Header | None = None
    reads: int = 0

    def parse(self, rgb: np.ndarray) -> header_mod.Header:
        crop = header_mod.crop_header(rgb, header_mod.HEADER_BOX_TALL)
        small = cv2.resize(crop, (64, 16), interpolation=cv2.INTER_AREA).astype(np.float32)
        if (
            self.header is not None
            and self.signature is not None
            and float(np.abs(small - self.signature).max()) < HEADER_CHANGE
        ):
            return self.header
        self.signature = small
        self.header = header_mod.parse(rgb)
        self.reads += 1
        return self.header


def _detect(frame: Frame, report: ScanReport) -> list[Tile] | None:
    tiles, _method = detect_tiles(frame.rgb, frame.grey())
    if len(tiles) < MIN_TILES_PER_FRAME:
        report.frames_skipped += 1
        report.skipped_reasons.append(f"{frame.source}: only {len(tiles)} tiles detected")
        return None
    return tiles


def _read_panel(
    frame: Frame,
    tiles: list[Tile],
    memo: SelectionMemo,
    scrolled: bool = True,
    on_start: Callable[[], None] | None = None,
    lines_out: list[tuple[float, str, float]] | None = None,
    with_holder: bool = False,
) -> tuple[int, Panel] | None:
    """(selected tile index, panel) when a tile is selected and not read yet.

    `with_holder` (the 武器 tab) also reads the "X装配中" strip below the panel.
    """
    from ..ocr.panel import read_holder, read_panel

    chosen = selected_index(frame.rgb, tiles)
    if chosen is None:
        return None
    boxes = [t.box for t in tiles]
    if not memo.needs_read(describe(tiles[chosen].icon), tiles[chosen].box, scrolled):
        return None
    if on_start is not None:
        on_start()
    panel = read_panel(frame.rgb, boxes, lines_out)
    if panel is None or panel.confidence < MIN_PANEL_CONFIDENCE:
        memo.result(attached=False)  # unreadable counts as a try, or it loops
        return None
    if with_holder:
        panel = replace(panel, holder=read_holder(frame.rgb, boxes))
    return chosen, panel


def _new_selection(frame: Frame, memo: SelectionMemo) -> list[Tile] | None:
    """The frame's tiles when a selection needing a panel read is visible."""
    tiles, _ = detect_tiles(frame.rgb, None)
    if len(tiles) < MIN_TILES_PER_FRAME:
        return None
    chosen = selected_index(frame.rgb, tiles)
    if chosen is None:
        return None
    tile = tiles[chosen]
    if memo.is_same(describe(tile.icon), tile.box, scrolled=False) and memo.settled:
        return None
    return tiles


#: A tile count this confident may confirm a panel read.
MIN_PANEL_MATCH_CONFIDENCE = 0.50


#: How sure the reference icons must be that a weapon tile is ANOTHER weapon for its
#: panel to be refused (D165): the margin between the best name and the next. Live,
#: 永远的启明星's tile was 0.13 clear of the rest; look-alikes sit far below 0.05.
PICTURE_SURE = 0.05


def _panel_agrees(
    panel: Panel, count: int | None, confidence: float, level: int | None = None,
    picture: Match | None = None, holder: HolderRead | None = None,
) -> bool:
    """True only when the panel demonstrably belongs to the selected tile.

    Fail closed (D32). The old rule only VETOED on a confident mismatch, and let
    anything else through: live, the outline moved a moment after the panel, the
    selected tile's count read at 0.86, and 撞金合剂 x9 was written onto the
    特级营养块 x23 tile. Counts are printed in full on tiles (63783 observed), so
    an honest match is always available; when it is not, attach nothing -- the
    user sees "click again" rather than a wrong name.

    A weapon panel has no 拥有 at all, so every click on the 武器 tab was refused
    and names like 奇幻变奏 never attached (D64). It prints 等级 90/90 instead,
    and the tile prints "Lv. 90": that pair is the same kind of proof.

    Not proof enough alone (D165): every finished weapon is Lv. 90, and on 2026-10-12 a
    panel about 云琅 was taken for the 永远的启明星 beside it -- learned three times, and
    every scan after named that sword 云琅. So a weapon's panel must also not contradict
    the tile's other witnesses: its 谐振 number, the face of who holds it (when that face
    has a name), and the reference icons when they are sure the tile is another weapon.
    """
    if level is not None and panel.level is not None:
        if level != panel.level:
            return False
        sure = count is not None and confidence >= MIN_PANEL_MATCH_CONFIDENCE
        if panel.rank is not None and sure and count != panel.rank:
            return False
        if holder is not None and holder.name and panel.holder and holder.name != panel.holder:
            return False
        return not (picture is not None and not picture.learned and picture.item_name
                    and picture.item_name != panel.name and picture.margin >= PICTURE_SURE)
    if panel.owned is None or count is None or confidence < MIN_PANEL_MATCH_CONFIDENCE:
        return False
    return stack_matches(count, panel.owned)


#: The most one tile holds. Above it an item splits into full stacks plus one
#: remainder tile, and `拥有` is their TOTAL: live, 特级调谐器 拥有 24629 showed as
#: tiles of 9999, 9999 and 4631 (D39).
MAX_STACK = 9999


def stack_matches(count: int, owned: int) -> bool:
    """Could a tile showing `count` be one stack of an item with `owned` in total?

    A full stack matches any total that fills it; the remainder tile matches when
    the rest is whole stacks (24629 = 9999 + 9999 + 4631).
    """
    if count > owned:
        return False
    return count == MAX_STACK or (owned - count) % MAX_STACK == 0


#: The tab whose tiles carry a level and a holder instead of a count (D61).
WEAPON_TAB = "武器"


def _weapon_reads(
    tiles: list[Tile],
    report: ScanReport,
    holders: Holders | None,
    read_counts: bool,
    count_only: int | None,
) -> tuple[list[int | None], list[HolderRead]]:
    """Per tile on the 武器 tab: its level, and who is carrying it (D61).

    A level of None means the tile is not a weapon at all -- the tab also holds
    the weapon EXP materials, which are ordinary bag tiles -- so the caller falls
    back to the bag layout for it. The portrait is only read for real weapons.

    Levels are read exactly where counts are, `count_only` included: the level
    says WHICH crop holds the count, so reading one without the other would take
    the count off the wrong place. The portraits ride along in one batch.
    """
    blank = [HolderRead() for _ in tiles]
    if not read_counts or (report.tab_label or "") != WEAPON_TAB:
        return [None] * len(tiles), blank
    levels = [
        read_level(tile.level_crop)[0] if count_only is None or index == count_only else None
        for index, tile in enumerate(tiles)
    ]
    if holders is None or not holders.available:
        return levels, blank
    return levels, holders.read([
        tile.holder_crop if level is not None else None
        for tile, level in zip(tiles, levels, strict=True)
    ])


#: Above this rarity a weapon only comes from a convene, so the pull history is
#: a list of the ones a tile can be. 4-star and below are also forged, bought and
#: handed out, and the history says nothing about those (D101).
PULL_ONLY_RARITY = 5


def _pulled_weapons(store: Store, report: ScanReport) -> frozenset[str] | None:
    """Weapons in the user's pull import, or None when there is nothing to check
    against: another tab, or no import yet."""
    if (report.tab_label or "") != WEAPON_TAB:
        return None
    pulls = store.pulls()
    if pulls and pulls.get("unknown"):
        # Ids nobody had named when this was imported and that are named now: the
        # pages fold them in, and so must the scan. Read as stored, an import
        # taken before the names shipped held one weapon, and every other 5-star
        # in the bag was "never pulled" and sent to a click.
        pulls = resolve_pulls(pulls, Catalogue.load())
    if not pulls or not pulls.get("weapons"):
        return None
    return frozenset(pulls["weapons"])


def _known_at_import(store: Store, report: ScanReport) -> frozenset[str] | None:
    """The weapons the catalogue knew when the pull history was imported (D179), or None:
    another tab, no import, or an import from before this was kept."""
    if (report.tab_label or "") != WEAPON_TAB:
        return None
    known = (store.pulls() or {}).get("weapons_known")
    return frozenset(known) if known else None


def _never_pulled(
    name: str, rarity: int, match: object, pulled: frozenset[str] | None,
    known: frozenset[str] | None = None,
) -> bool:
    """Is this a 5-star weapon named from catalogue artwork alone, which the pull
    history says was never pulled (D101)?

    千古洑流 was read as 苍鳞千嶂 -- a 长刃 the user never had -- at 0.71 with the
    right icon gated out on hue. Artwork is not enough against that; the panel is,
    so a name the panel gave a crop like this one (`learned`) is not doubted: the
    handful of 5-star weapons given away outside the convene cost one click, once.

    `known`, the weapons the catalogue had when the history was imported (D179): one
    newer than that -- 沉冥, fetched with a wiki update after the import -- cannot be in
    it, and is not doubted for that.
    """
    return (
        pulled is not None
        and rarity >= PULL_ONLY_RARITY
        and name not in pulled
        and (known is None or name in known)
        and not getattr(match, "learned", False)
        and name in weapon_names()
    )


def _ingest(
    frame: Frame,
    tiles: list[Tile],
    store: Store,
    report: ScanReport,
    gallery: Gallery | None,
    read_counts: bool,
    seen: set[str],
    stitcher: Stitcher,
    panel: tuple[int, Panel] | None = None,
    count_only: int | None = None,
    holders: Holders | None = None,
) -> list[Observation]:
    """Read, stitch and persist one frame's tiles. Returns its observations.

    `count_only` limits count OCR to that one tile: a click view needs only the
    selected tile's count, and the others were read a moment ago (~2.5 s saved).

    Stitching happens BEFORE the rows are written, so each row can record which
    item it is (`item_key`) -- the icon hash cannot say that for live frames.
    """
    matches: list[object | None] = [None] * len(tiles)
    vectors = None
    looks = [describe(t.icon) for t in tiles]  # stitching: shape + colour thumbnail
    hues = [hue_signature(t.icon) for t in tiles]  # gallery: hue only (D30)
    if gallery is not None:
        # Embed once: the same vectors serve the query and the gallery write.
        # Embedding twice was ~3 s of a ~10 s view on CPU.
        vectors = gallery.encoder.embed([t.icon for t in tiles])
        matches = gallery.query(
            [t.icon for t in tiles], [t.rarity.rarity for t in tiles],
            vectors=vectors, colours=hues, looks=looks,
        )
    report.last_matches = list(matches)

    levels, holder_reads = _weapon_reads(tiles, report, holders, read_counts, count_only)
    pulled = _pulled_weapons(store, report)
    known = _known_at_import(store, report)

    rows: list[Observation] = []
    panel_used = False
    for index, tile in enumerate(tiles):
        digest = icon_hash(tile.icon)
        if digest not in seen:
            store.save_icon(digest, tile.icon)
        seen.add(digest)

        level, holder = levels[index], holder_reads[index]
        if holder.key is not None and tile.holder_crop is not None:
            store.save_icon(holder.key, tile.holder_crop)  # the 武器 page shows it
        skipped = not read_counts or (count_only is not None and index != count_only)
        # The number on a weapon tile is that copy's 谐振阶数, and it sits inside
        # the artwork; the footer the bag reader would use holds "Lv. 90" (D61).
        crop, alts = (
            (tile.rank_crop, tile.rank_alts) if level is not None
            else (tile.count_crop, tile.count_alts)
        )
        count, confidence = (None, 0.0) if skipped or crop is None else read_tile_count(crop, alts)
        agrees = panel is not None and panel[0] == index and _panel_agrees(
            panel[1], count, confidence, level, picture=matches[index], holder=holder
        )
        if panel is not None and panel[0] == index and not agrees:
            report.panel_unmatched = panel[1]
        if panel is not None and agrees:
            # The game's own words about this tile: name and `拥有 N` (D24).
            read = panel[1]
            report.panel_reads += 1
            report.last_panel = read
            panel_used = True
            # This tile's own count: equal to 拥有 unless the item spans stacks.
            if level is not None and count is None and read.rank is not None:
                # The tile's number was unreadable; the panel prints it too ("1阶").
                count, confidence = read.rank, read.confidence
            if level is not None and read.category in weapon_types():
                # "音感仪", the game saying what kind of weapon this is: kept for
                # the weapons the wiki's build pages do not list (D98).
                store.learn_weapon_kind(read.name, read.category)
            if level is not None and holder.key is not None and holders is not None:
                # "达妮娅装配中" under the panel: the game naming the portrait for
                # us, which no likeness could (D64).
                named = holders.name_face(holder.key, read.holder)
                if named:
                    holder = replace(holder, name=named)
                    report.holders_named += 1
            rows.append(
                Observation(
                    frame=f"{frame.source.strip()}#{frame.seq}",
                    row=tile.row, col=tile.col, icon_hash=digest,
                    rarity=tile.rarity.rarity, rarity_conf=tile.rarity.confidence,
                    count=count,
                    count_conf=max(confidence, read.confidence),
                    # A weapon panel has no 拥有 line -- each copy is its own tile --
                    # so a missing one is not a count to review (D96).
                    item_name=read.name,
                    needs_review=read.owned is None and level is None,
                    box=tile.box, descriptor=looks[index], from_panel=True,
                    level=level, holder_key=holder.key,
                )
            )
            continue

        needs_review = not skipped and (count is None or confidence < MIN_COUNT_CONFIDENCE)

        item_name = None
        match = matches[index]
        rivals = tuple(getattr(match, "rivals", ()) or ()) if match is not None else ()
        if match is not None and getattr(match, "confident", False):
            item_name = getattr(match, "item_name", None)
            # A tile with a level is a weapon, so only a weapon name may land on
            # it: 悲喜剧, which is not one, had been written onto one (D65).
            known = weapon_names() if level is not None and item_name else frozenset()
            if known and item_name not in known:
                item_name = None
            elif item_name and _never_pulled(item_name, tile.rarity.rarity, match, pulled,
                                             known):
                # Not asserted: offered beside the next-best name, for a click.
                runner_up = getattr(match, "runner_up", None)
                rivals = (item_name, runner_up) if runner_up else rivals
                item_name = None
                report.doubted += 1
            if item_name:
                report.identified += 1
            else:
                report.unnamed += 1
        elif gallery is not None:  # noqa: SIM114 -- the two branches differ in meaning
            # Unidentified or low-margin: queue for hover fallback rather than
            # guess (D15 fail open on data). Deliberately NOT folded into
            # needs_review -- conflating "count unreadable" with "name unknown"
            # hides count quality, which is the metric the scanner is judged on.
            report.unnamed += 1

        rows.append(
            Observation(
                frame=f"{frame.source.strip()}#{frame.seq}",
                row=tile.row,
                col=tile.col,
                icon_hash=digest,
                rarity=tile.rarity.rarity,
                rarity_conf=tile.rarity.confidence,
                count=count,
                count_conf=confidence,
                item_name=item_name,
                needs_review=needs_review,
                box=tile.box,
                descriptor=looks[index],
                rivals=rivals,
                level=level,
                holder_key=holder.key,
            )
        )
        report.needs_review += needs_review

    stitcher.header_total = report.header_total
    stitcher.add_frame(rows)
    rows = [replace(r, item_key=k) for r, k in zip(rows, stitcher.obs_keys, strict=True)]
    store.add_observations(scan_id=report.scan_id, rows=rows)
    report.frames_used += 1
    report.tiles += len(rows)

    if gallery is not None:
        # Self-building gallery (D3): a crop never seen before is embedded and
        # stored, so a new patch item costs one encode, not a retrain.
        report.gallery_added += gallery.add(
            [t.icon for t in tiles],
            [icon_hash(t.icon) for t in tiles],
            [t.rarity.rarity for t in tiles],
            tab=report.tab_label,
            vectors=vectors,
            colours=hues,
        )
        if panel_used:
            # Name the crop the panel described, so the NEXT scan names this item
            # from the gallery without anyone clicking it again.
            gallery.name_item(icon_hash(tiles[panel[0]].icon), panel[1].name)
        # Every crop of a panel-confirmed item carries its name, not only the
        # selected one: learned names now only pass to look-alike crops (D37).
        for key in dict.fromkeys(stitcher.obs_keys):
            item = stitcher.items.get(key)
            if item is not None and item.confirmed and item.item_name:
                gallery.name_crops(store.item_crops(report.scan_id, key), item.item_name)
        gallery.load()
    return rows


def _process_frame(
    frame: Frame,
    store: Store,
    scan_id: int,
    report: ScanReport,
    gallery: Gallery | None,
    read_counts: bool,
    seen: set[str],
    stitcher: Stitcher,
    holders: Holders | None = None,
) -> list[Observation]:
    """Fixture path: detect, read the header once, ingest."""
    tiles = _detect(frame, report)
    if tiles is None:
        return []
    if report.header_total is None:
        head = header_mod.parse(frame.rgb)
        report.header_total = head.unique_items
        report.tab_label = head.label
        _read_wallet(frame.rgb, store)
    return _ingest(
        frame, tiles, store, report, gallery, read_counts, seen, stitcher, holders=holders
    )


#: Below this the currency read is not kept (fail open on data, but not on noise).
MIN_WALLET_CONFIDENCE = 0.8


def _read_wallet(rgb: np.ndarray, store: Store) -> None:
    """贝币 / 星声 off the top bar (D48). Never lets a failed read stop a scan."""
    try:
        cash = currency_mod.parse(rgb)
    except Exception:  # noqa: BLE001 -- the wallet is a bonus, the scan is the job
        return
    if cash.shells is not None and cash.confidence >= MIN_WALLET_CONFIDENCE:
        store.add_wallet(cash.shells, cash.astrite, cash.confidence)


def _finalise(store: Store, report: ScanReport, stitcher: Stitcher) -> None:
    report.unique = stitcher.unique
    stitcher.header_total = report.header_total
    store.conn.execute(
        "UPDATE scan SET tab_label=?, header_total=? WHERE id=?",
        (report.tab_label, report.header_total, report.scan_id),
    )
    store.finish_scan(report.scan_id, report.frames_used, report.tiles, report.complete)


def run_scan(
    frames: Iterable[Frame],
    store: Store,
    source: str,
    *,
    read_counts: bool = True,
    gallery: Gallery | None = None,
    holders: Holders | None = None,
) -> ScanReport:
    """Process a finite sequence of frames into one append-only scan snapshot."""
    scan_id = store.begin_scan(source, None, None)
    report = ScanReport(scan_id=scan_id)
    stitcher = Stitcher()
    seen: set[str] = set()

    for frame in frames:
        _process_frame(
            frame, store, scan_id, report, gallery, read_counts, seen, stitcher, holders
        )

    report.stop_reason = "end of frames"
    _finalise(store, report, stitcher)
    return report


# ------------------------------------------------------------------ live


@dataclass
class TabScan:
    """One bag tab's scan: its own report, stitcher and header count."""

    report: ScanReport
    stitcher: Stitcher = field(default_factory=Stitcher)
    seen: set[str] = field(default_factory=set)
    closed: bool = False
    """Finished in the database and handed over while the session went on (D173)."""

    @property
    def label(self) -> str | None:
        return self.report.tab_label


@dataclass
class TabBook:
    """The tabs of one live session (D24), and which of them are done (D173).

    A tab left COMPLETE -- the game's header count reached -- is closed then: finished in
    the database, so it can be sent home while the session goes on (`on_close`). Coming back
    to a closed tab goes on with it under a new scan number, its rows and stitching carried
    over: a look back at a few items leaves the tab complete and newer, never "3 of 155".
    A tab left unfinished stays open, as it always did, and is finished at the end.
    """

    store: Store
    source: str
    tabs: list[TabScan]
    on_close: Callable[[TabScan], None] | None = None

    @classmethod
    def start(cls, store: Store, source: str,
              on_close: Callable[[TabScan], None] | None = None) -> TabBook:
        first = TabScan(ScanReport(scan_id=store.begin_scan(source, None, None)))
        return cls(store, source, [first], on_close)

    def switch_to(self, label: str) -> TabScan:
        for i, tab in enumerate(self.tabs):
            if tab.label == label:
                if tab.closed:
                    tab = self._reopen(tab)
                    self.tabs[i] = tab
                self.tabs.append(self.tabs.pop(i))  # most recent last
                return tab
        fresh = self.tabs[-1]
        if fresh.label is not None or fresh.report.frames_used:
            fresh = TabScan(ScanReport(scan_id=self.store.begin_scan(self.source, None, None)))
            self.tabs.append(fresh)
        fresh.report.tab_label = label
        return fresh

    def _reopen(self, done: TabScan) -> TabScan:
        scan_id = self.store.begin_scan(self.source, None, None)
        self.store.copy_observations(done.report.scan_id, scan_id)
        report = replace(done.report, scan_id=scan_id, stop_reason="", aborted=False)
        return TabScan(report, done.stitcher, done.seen)

    def leave(self, tab: TabScan) -> None:
        """`tab` is no longer in view: closed and handed over if it is complete."""
        if tab.closed or tab.label is None or not tab.stitcher.complete:
            return
        tab.report.stop_reason = "complete per header count"
        _finalise(self.store, tab.report, tab.stitcher)
        tab.closed = True
        if self.on_close is not None:
            self.on_close(tab)

    def finish(self, reason: str, aborted: bool) -> None:
        """The session is over: every tab still open is finished, as it was."""
        for tab in self.tabs:
            if tab.closed:
                continue
            tab.report.aborted = aborted
            tab.report.stop_reason = reason
            _finalise(self.store, tab.report, tab.stitcher)


class Stopwatch:
    """Seconds per stage of reading one view, for the run record."""

    def __init__(self, moved_at: float | None) -> None:
        self.start = self.mark = time.monotonic()
        self.times = {"settle": round(self.start - moved_at, 3) if moved_at else 0.0}

    def lap(self, stage: str) -> None:
        now = time.monotonic()
        self.times[stage] = round(now - self.mark, 3)
        self.mark = now

    def done(self) -> dict[str, float]:
        self.times["total"] = round(self.mark - self.start, 3)
        return self.times


@dataclass(frozen=True)
class View:
    """One view that was read: what `on_view` receives.

    `tiles` and `rows` are aligned index for index; each row's `item_key` says
    which stitched item that tile is.
    """

    tab: TabScan
    frame: Frame
    tiles: list[Tile]
    rows: list[Observation]
    tabs: list[TabScan]
    """Every tab in this session, most recent last."""
    matches: list[object | None] = field(default_factory=list)
    """Gallery match per tile (aligned with `tiles`), for showing scores."""
    panel: Panel | None = None
    """The detail panel read on this view, attached or not."""
    timings: dict[str, float] = field(default_factory=dict)
    """Seconds spent per stage, plus `settle` (last motion -> accepted)."""
    novelty: float = 0.0
    """How different this view was from the previous read one (gate units)."""


@dataclass
class LiveResult:
    """Every tab visited during one live session, most recent last.

    Unpacks as `(report, stitcher)` of the tab in view when the scan stopped, which
    is all a single-tab caller needs.
    """

    tabs: list[TabScan]
    stop_reason: str = ""
    aborted: bool = False

    @property
    def current(self) -> TabScan:
        return self.tabs[-1]

    @property
    def report(self) -> ScanReport:
        return self.current.report

    @property
    def stitcher(self) -> Stitcher:
        return self.current.stitcher

    def __iter__(self) -> Iterator[object]:
        return iter((self.report, self.stitcher))


def run_live_scan(
    frames: Iterable[Frame],
    store: Store,
    source: str,
    *,
    gallery: Gallery | None = None,
    gate: FrameGate | None = None,
    panic: PanicKey | None = None,
    max_seconds: float = 1200.0,
    stop_when_complete: bool = True,
    focus_ok: Callable[[], bool] | None = None,
    focus_grace: float = 120.0,
    on_focus_change: Callable[[bool], None] | None = None,
    on_view: Callable[[View], None] | None = None,
    on_tab: Callable[[TabScan], None] | None = None,
    on_tab_closed: Callable[[TabScan], None] | None = None,
    read_panel: bool = True,
    holders: Holders | None = None,
    skip_tabs: Iterable[str] = DEFAULT_SKIP_TABS,
    on_skip: Callable[[str], None] | None = None,
    on_phase: Callable[[str], None] | None = None,
    on_frame: Callable[[Frame], None] | None = None,
    on_event: Callable[[str, dict[str, object]], None] | None = None,
) -> LiveResult:
    """Drive the pipeline from live capture.

    Stops on, in priority order: the panic key, focus lost for longer than
    `focus_grace`, the tab in view reaching its header count (only when
    `stop_when_complete`), the time budget, or the frame source ending.

    The panic and focus checks run on EVERY captured frame, not only on gated ones
    -- a guardrail that only fires when the picture happens to be stable is not a
    guardrail. `focus_ok` is injected rather than imported so this module stays
    OS-free and testable; the CLI passes `is_game_foreground`.

    **Tabs (D24).** The header is re-read on every view. Each tab (资源, 素材, 补给
    ...) is its own scan with its own header count, so switching tabs mid-session
    starts or resumes that tab instead of piling a second tab's items onto the
    first one's count. `on_tab` fires on every switch. A tab left complete is closed then
    and `on_tab_closed` gets it, to be sent home while the scan goes on (D173, `TabBook`).

    **Detail panel (D24).** When a tile is selected -- the user clicked it -- the
    panel's name and `拥有 N` are read and attached to that tile. They outrank tile
    OCR and the gallery, and the name is written back to the gallery.

    **Skipped tabs (D28).** A view whose header matches `skip_tabs` is dropped
    before anything is read or stored; `on_skip` fires once on entering such a tab.
    While in one, a view with an unreadable header is dropped too, rather than
    credited to the last scanned tab.

    **Phase (D32).** `on_phase` reports what the scanner is doing, so the user
    knows when to act: "moving" (screen still changing), "settling" (still, not
    yet accepted), "reading" / "reading-panel" (OCR in progress -- hold still),
    "ready" (done; scroll or click the next item), "paused" (game not in front).
    Fired on change only.

    `on_view` fires after every frame that was actually read, with a `View`; the
    tab's stitcher holds that frame's new items in `last_new`.

    `on_frame` sees every focused frame, read or not (the live preview).
    `on_event` gets diagnostics: ("repeat", {novelty}) once per still spell whose
    frame was dropped as unchanged -- a click the gate did not see shows up here.

    Losing focus PAUSES rather than aborts (D22); focus gone past `focus_grace`
    stops the scan. `focus_grace=0` restores the strict D15 reading.
    """
    from ..capture.gating import FrameGate as _FrameGate

    gate = gate or _FrameGate()
    deadline = time.monotonic() + max_seconds
    book = TabBook.start(store, source, on_close=on_tab_closed)
    tabs = book.tabs
    result = LiveResult(tabs=tabs)
    memo = SelectionMemo()
    probed_at = 0.0
    header_memo = HeaderMemo()


    phase: list[str | None] = [None]

    def set_phase(p: str) -> None:
        if p != phase[0]:
            phase[0] = p
            if on_phase is not None:
                on_phase(p)

    unfocused_since: float | None = None
    skip_tabs = tuple(skip_tabs)
    skipping: str | None = None

    for frame in frames:
        if panic is not None and panic.triggered:
            result.aborted = True
            result.stop_reason = "panic key"
            break
        if time.monotonic() > deadline:
            result.stop_reason = f"time budget ({max_seconds:.0f}s) reached"
            break

        if focus_ok is not None and not focus_ok():
            set_phase("paused")
            result.current.report.frames_unfocused += 1
            now = time.monotonic()
            if unfocused_since is None:
                unfocused_since = now
                # Make the gate re-settle on return: the frames spanning a focus
                # change are exactly the ones that lie about the grid being still.
                gate.reset()
                if on_focus_change is not None:
                    on_focus_change(False)
            elif now - unfocused_since >= focus_grace:
                result.stop_reason = f"focus lost for over {focus_grace:.0f}s"
                break
            continue
        if unfocused_since is not None:
            unfocused_since = None
            if on_focus_change is not None:
                on_focus_change(True)

        if on_frame is not None:
            on_frame(frame)
        before = (gate.stats.moving, gate.stats.settling, gate.stats.repeat)
        gated = gate.offer(frame)
        probed: list[Tile] | None = None
        if gated is None and gate.stats.repeat > before[2] and read_panel:
            # Still and unchanged. A click changes too little of the screen for
            # the gate (the outline, a strip of the panel), so look for it: is a
            # different tile selected than the panel was last read for?
            now = time.monotonic()
            if now - probed_at >= SELECTION_PROBE:
                probed_at = now
                probed = _new_selection(frame, memo)
                if probed is not None:
                    gated = frame
                    gate.accept(frame)
                    if on_event is not None:
                        on_event("selection", {})
        if gated is None:
            if gate.stats.repeat > before[2] and phase[0] != "ready" and on_event is not None:
                on_event("repeat", {"novelty": round(gate.last_novelty, 3)})
            if gate.stats.moving > before[0]:
                set_phase("moving")
            elif gate.stats.settling > before[1]:
                set_phase("settling")
            else:
                set_phase("ready")
            continue
        set_phase("reading")
        watch = Stopwatch(gate.moved_at)
        scrolled = probed is None
        tiles = probed if probed is not None else _detect(gated, result.current.report)
        watch.lap("detect")
        if tiles is None:
            continue

        # A click changes nothing in the header: keep the last read (~2 s saved).
        reads = header_memo.reads
        head = (
            header_memo.header
            if not scrolled and header_memo.header is not None
            else header_memo.parse(gated.rgb)
        )
        if header_memo.reads != reads:  # the bar was re-read: so is the wallet (D48)
            _read_wallet(gated.rgb, store)
        watch.lap("header")
        if is_skipped(head.label, skip_tabs):
            if head.label != skipping:
                book.leave(result.current)        # left for a tab not scanned (D173)
                if on_skip is not None:
                    on_skip(head.label)
            skipping = head.label
            memo.ignore(gated.rgb, tiles, scrolled)
            continue
        if head.label is None and skipping is not None:
            memo.ignore(gated.rgb, tiles, scrolled)
            continue  # still on the skipped tab as far as we can tell
        entered_from_skip = skipping is not None
        skipping = None

        tab = result.current
        misread = (
            # Same count, never-seen label: an OCR slip on the SAME tab (资源 read
            # as 过 on one capture), not a switch. A real switch changes the count
            # or lands on a label already visited.
            tab.label is not None
            and head.label != tab.label
            and head.unique_items is not None
            and head.unique_items == tab.report.header_total
            and all(t.label != head.label for t in tabs)
        )
        if misread:
            head = replace(head, label=tab.label)
        if head.label is not None and (head.label != tab.label or entered_from_skip):
            left, tab = tab, book.switch_to(head.label)
            if left is not tab:
                book.leave(left)
            if on_tab is not None:
                on_tab(tab)
        if head.unique_items is not None:
            # Always the game's latest number: it changes if an item runs out.
            tab.report.header_total = head.unique_items

        attempt: list[tuple[float, str, float]] = []
        panel = (
            _read_panel(gated, tiles, memo, scrolled,
                        on_start=lambda: set_phase("reading-panel"), lines_out=attempt,
                        with_holder=tab.label == WEAPON_TAB)
            if read_panel
            else None
        )
        tab.report.panel_attempt = attempt or None
        # User name corrections (D40): a misread is rewritten on every read, and
        # items already named with the misread are renamed in place.
        aliases = store.aliases()
        if panel is not None:
            # A hand fix wins; otherwise snap onto the official catalogue (D42).
            read_name = panel[1].name
            fixed = aliases.get(read_name) or snap(read_name, catalogue_names())
            if fixed != read_name:
                panel = (panel[0], replace(panel[1], name=fixed))
        if aliases:
            for item in tab.stitcher.items.values():
                if item.item_name in aliases:
                    item.item_name = aliases[item.item_name]
        watch.lap("panel")
        tab.report.last_panel = None
        tab.report.panel_unmatched = None
        rows = _ingest(
            gated, tiles, store, tab.report, gallery, True, tab.seen, tab.stitcher, panel,
            count_only=None if scrolled else (panel[0] if panel else -1),
            holders=holders,
        )
        watch.lap("ingest")
        if panel is not None:
            # Not attached (outline and panel out of step, or an unread count):
            # the probe retries it, up to MAX_PANEL_TRIES for this selection.
            memo.result(attached=tab.report.panel_unmatched is None)
        if rows and on_view is not None:
            on_view(View(
                tab=tab, frame=gated, tiles=tiles, rows=rows, tabs=tabs,
                matches=tab.report.last_matches, panel=panel[1] if panel else None,
                timings=watch.done(), novelty=round(gate.last_novelty, 3),
            ))
        set_phase("ready")

        if stop_when_complete and tab.stitcher.complete:
            result.stop_reason = "complete per header count"
            break
    else:
        result.stop_reason = result.stop_reason or "capture ended"

    book.finish(result.stop_reason, result.aborted)
    return result


def scan_path(
    path: Path | str,
    store: Store,
    *,
    read_counts: bool = True,
    gallery: Gallery | None = None,
    holders: Holders | None = None,
) -> ScanReport:
    """Convenience: scan a fixture file or directory."""
    from ..capture.file_backend import FileCapture

    cap = FileCapture(path)
    return run_scan(
        cap.frames(), store, source=str(path), read_counts=read_counts, gallery=gallery,
        holders=holders,
    )
