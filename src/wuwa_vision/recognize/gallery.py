# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Embedding gallery: open-set item identity by nearest neighbour.

Combines three things:

* wucv's `EmbeddingStore` sync semantics -- embeddings are cached and only
  recomputed when the underlying crop actually changes, and the cache is
  invalidated wholesale when the embedding space changes (model, preprocessing,
  or dimensionality). Getting that check wrong silently mixes incompatible
  vectors, which is worse than recomputing.
* This project's **rarity gating** (PLAN.md D3): search only within the query's
  own rarity. That removes the tier-variant confusion class outright, since WuWa
  maps material tiers onto rarity colours. It buys nothing for 1-star items --
  the flowers/ingredients bucket is the largest and is all one rarity -- so the
  embedding still carries that load alone.
* This project's **confidence margin**: identity is only asserted when the top
  match clearly beats the runner-up. Otherwise the tile is flagged for hover
  fallback rather than guessed (D15: fail open on data, never promote a guess).

Storage is the SQLite `gallery` table, keyed by icon content hash, so a crop seen
again costs a lookup rather than a forward pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np

from ..store.db import Store
from .appearance import (
    HUE_BINS,
    LOOK_GAP,
    MIN_HUE_MASS,
    describe,
    hue_signature,
    is_the_other,
)
from .encoder import IconEncoder
from .pack import NO_PICTURE
from .reference import RARITY_ANY

#: Minimum cosine similarity for the top hit to be considered at all.
#:
#: This is a WEAK gate and must not be relied on for novelty rejection. DINOv2
#: similarity between *different* WuWa icons routinely reaches 0.92-0.99 because
#: they share an art style (observed wrong matches at 0.987, 0.952, 0.925). Open-set
#: rejection -- deciding that a query is simply absent from the gallery -- is NOT
#: solved by a similarity floor, and is an open problem (see PLAN.md).
MIN_SIMILARITY = 0.60
#: Minimum gap between best and second-best before identity is asserted.
#: Calibrated on wucv's labelled set with dinov2-base (an adversarial slice --
#: mostly tier variants of the same shapes):
#:     margin 0.00 -> 84.6% precision, 0% fallback
#:     margin 0.02 -> 95.2% precision, 35% fallback
#:     margin 0.08 -> 100%  precision, 69% fallback
#: 0.02 is the knee. Real inventories are far more diverse than that slice, so the
#: true fallback rate should be much lower -- but it must be MEASURED on real
#: scans before D10's phase-2 decision, not assumed from this number.
MIN_MARGIN = 0.02
#: A gallery entry cut from the game screen only matches a query of the same hue.
#: DINOv2 is nearly colour-blind: one panel-learned name (湮灭干涉混悬液) spread to
#: every element variant of that potion. Same-item crops score >= 0.946 on
#: `appearance.same_hue`, the variants 0.0-0.2 (D30). Screen-cut entries only:
#: reference icons come from a website render, and are left to shape + rarity.
MIN_HUE = 0.80
#: A catalogue picture shut out on hue by less than this much -- 0.70 to MIN_HUE -- that
#: still scores clearly above the winner makes the match a question, not an answer (D195).
#: The user's 千古洑流 tile was 0.799 to its own picture and was written 浩境粼光, sure; on
#: this PC's scans 44 of the 56 tiles doubted this way were 千古洑流 written as another.
#: Colour variants sit far below (0.0-0.2), so this never reopens what D30 closed.
NEAR_HUE = 0.70
#: ... and one shut out by more, when it is this much better than the winner: every picture
#: like the tile was gone and what was left won on a colourless picture -- 气动阻抗喷雾
#: written F型还原素 (0.653, its own picture 0.934). A colour variant beats its sibling by
#: ~0.03, so stays shut out; 0.10 would have doubted 漪澜浮录, read right in the panel.
FAR_GAP = 0.15
#: A tie between two DIFFERENT names is only reported as "these look identical"
#: when both are near-duplicates of the query. Below this the query is simply
#: unknown, not ambiguous. Twins with pixel-identical art score ~0.97 (D31).
TWIN_SIMILARITY = 0.90
#: Two gallery entries this alike are the same artwork. The catalogue has several
#: items drawn identically (撞金合剂 / 划音合剂, four 溶剂): a query tied between
#: them is a twin at ANY score -- screen-vs-catalogue scores sit near 0.84, under
#: TWIN_SIMILARITY, which was calibrated screen-vs-screen (D42).
SAME_ART = 0.99
#: A crop is the same item as the one a panel named only above this (D92). One
#: weapon's own crops score 0.94-0.9999 against each other across a whole scan
#: (selection outline included); a different weapon scored 0.75-0.82.
SAME_ITEM_CROP = 0.90
#: A name learned from the detail panel only passes to a crop that LOOKS like the
#: crop it was learned on (`appearance.describe`, colour + shape). DINOv2 said
#: 0.935 for 隐雷声核 vs 霍闪声核 -- inside the same-item range -- so with one of
#: the two named, the other took its name (D37). On `describe`, re-sightings of
#: one item score >= 0.99 (95%), distinct items at most 0.944 and that pair 0.90.
#: Pixel-identical twins still pass (~1.0) and are left to the rivals rule.
MIN_LOOK = 0.97
#: A screen crop named in the detail panel, matched this closely, is that very tile: the
#: colour rule for a dish and its special version leaves it alone (D193).
SAME_TILE = 0.98
#: ... and decides only a pair drawn alike: 蛋饼 / 青蔬蛋饼 0.92, 锅盔 / 糖心锅盔 0.95. A special
#: dish drawn differently (雾茗 / 喜凌茶) differs in colour everywhere, and the picture
#: model tells those apart already; colour renamed 40 of them on this PC's scans.
DRAWN_ALIKE = 0.90

@dataclass(frozen=True, slots=True)
class Match:
    """One retrieval result."""

    icon_hash: str
    item_name: str | None
    rarity: int
    score: float
    margin: float
    rivals: tuple[str, ...] = ()
    """When set, the query looks the same as ALL these named items -- identical-art
    twins such as 撞金合剂 / 划音合剂. Only the detail panel can tell them apart."""
    learned: bool = False
    """The winning entry is a crop cut from the game screen, so its name is one the
    detail panel gave a tile like this -- not a catalogue icon's (D101)."""
    runner_up: str | None = None
    """The best-scoring DIFFERENT name: what to offer beside a doubted match."""

    @property
    def ambiguous(self) -> bool:
        return len(self.rivals) >= 2

    @property
    def confident(self) -> bool:
        """True only when this match can actually NAME the item.

        An unnamed gallery entry is a de-duplication anchor, not an identification:
        the self-building gallery adds every unseen crop, so matching one proves
        nothing about identity until the hover bootstrap attaches a real name.
        Counting unnamed matches as identifications produced 25 false positives on
        a 72-item scan where every item was distinct.
        """
        return (
            self.item_name is not None
            and self.score >= MIN_SIMILARITY
            and self.margin >= MIN_MARGIN
        )

    @property
    def is_duplicate(self) -> bool:
        """Strong match to a known crop -- usable for de-dup regardless of naming."""
        return self.score >= MIN_SIMILARITY and self.margin >= MIN_MARGIN


class Gallery:
    """Rarity-gated nearest-neighbour index over stored icon embeddings."""

    def __init__(self, store: Store, encoder: IconEncoder) -> None:
        self.store = store
        self.encoder = encoder
        self._hashes: list[str] = []
        self._names: list[str | None] = []
        self._twins: dict[str, tuple[str, ...]] = {}
        self._rarities: np.ndarray = np.zeros(0, dtype=np.int16)
        self._matrix: np.ndarray = np.zeros((0, 0), dtype=np.float32)
        self._colours: np.ndarray = np.zeros((0, 0), dtype=np.float32)
        self._has_colour: np.ndarray = np.zeros(0, dtype=bool)
        self._looks: np.ndarray = np.zeros((0, 0), dtype=np.float32)
        self._has_look: np.ndarray = np.zeros(0, dtype=bool)
        self._look_cache: dict[str, np.ndarray | None] = {}
        self._variants: dict[str, frozenset[str]] = {}
        self._reference_look = None   # name -> `describe` of its catalogue picture (D201)
        self._ref_colour: dict[str, np.ndarray] = {}
        self._ref_vector: dict[str, np.ndarray] = {}

    # ---------------------------------------------------------------- loading

    def load(self) -> int:
        """Load embeddings for the CURRENT encoder only. Returns entry count."""
        key = self.encoder.info.key()
        rows = self.store.conn.execute(
            "SELECT icon_hash, item_name, rarity, embedding, colour, tab FROM gallery "
            "WHERE backbone = ? AND embedding IS NOT NULL ORDER BY icon_hash",
            (key,),
        ).fetchall()

        self._hashes = [r["icon_hash"] for r in rows]
        self._names = [r["item_name"] for r in rows]
        self._tabs = [r["tab"] for r in rows]
        self._rarities = np.array([r["rarity"] for r in rows], dtype=np.int16)
        if rows:
            dim = self.encoder.info.embedding_size
            self._matrix = np.stack(
                [np.frombuffer(r["embedding"], dtype=np.float32).reshape(dim) for r in rows]
            )
        else:
            self._matrix = np.zeros((0, self.encoder.info.embedding_size), dtype=np.float32)

        colours = [self._colour_of(r) for r in rows]
        self._has_colour = np.array([c is not None for c in colours], dtype=bool)
        self._colours = (
            np.stack([c if c is not None else np.zeros(HUE_BINS, np.float32) for c in colours])
            if colours
            else np.zeros((0, HUE_BINS), dtype=np.float32)
        )

        looks = [self._look_of(r) for r in rows]
        self._has_look = np.array([v is not None for v in looks], dtype=bool)
        dim = next((v.size for v in looks if v is not None), 0)
        self._looks = (
            np.stack([v if v is not None else np.zeros(dim, np.float32) for v in looks])
            if dim
            else np.zeros((len(rows), 0), dtype=np.float32)
        )
        self._twins = self._shared_artwork()
        self._ref_colour = {name: self._colours[i] for i, name in enumerate(self._names)
                            if name and self._tabs[i] == "reference" and self._has_colour[i]}
        self._ref_vector = {name: self._matrix[i] for i, name in enumerate(self._names)
                            if name and self._tabs[i] == "reference"}
        return len(self._hashes)

    def _shared_artwork(self) -> dict[str, tuple[str, ...]]:
        """name -> every name drawn the same way, when more than one is (D57).

        The catalogue draws several items identically (撞金合剂 / 划音合剂, the four
        溶剂, 糖醋汁 / 醋), same artwork AND same rarity. Once one of them is named --
        a panel read, or the user's own correction -- its crop wins any later match
        outright, and its twins
        would quietly take that name. A name in such a group therefore never names
        a crop: the match comes back with the group as its rivals, and the item
        waits for a click, every scan.
        """
        # Catalogue icons only (D92). Screen crops chain: a crop mis-named once
        # sits at 0.999 to a correctly named one, union-find joins the two names,
        # and one bad scan glued 14 unrelated weapons (and 高级能源核心) into a
        # single "drawn identically" group that sent every one of them to a click.
        # Identically drawn catalogue items are identical as reference icons, so
        # nothing D57 is for is lost.
        named = [i for i, name in enumerate(self._names)
                 if name is not None and self._tabs[i] == "reference"]
        if len(named) < 2:
            return {}
        block = self._matrix[named]
        same = (block @ block.T) >= SAME_ART
        parent: dict[str, str] = {}

        def root(x: str) -> str:
            while parent.setdefault(x, x) != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for a, b in zip(*np.nonzero(same), strict=True):
            i, j = named[int(a)], named[int(b)]
            one, two = self._names[i], self._names[j]
            # Same rarity only: 中级 / 高级营养块 share the artwork but not the
            # rarity bar, and the rarity gate already tells those apart.
            twins = one != two and one is not None and two is not None
            if twins and self._rarities[i] == self._rarities[j]:
                parent[root(one)] = root(two)
        groups: dict[str, list[str]] = {}
        for name in parent:
            groups.setdefault(root(name), []).append(name)
        return {name: tuple(sorted(g)) for g in groups.values() if len(g) > 1 for name in g}

    def fix_rarities(self, fixes: dict[str, dict[str, int]]) -> int:
        """Catalogue pictures embedded at a rarity Kuro's wiki has wrong take the game's (D199).

        A scanner seeded before a fix keeps each vector; only the rarity moves, and only where
        it is still the one fixed. Crops from the screen carry the rarity read off their bar,
        and are left alone. Returns how many entries changed."""
        changed = 0
        # Committed even when nothing matched: an UPDATE opens a transaction either way, and one
        # left open kept the write lock -- the scan's next connection was "database is locked".
        with self.store.conn:
            for name, fix in fixes.items():
                changed += self.store.conn.execute(
                    "UPDATE gallery SET rarity = ? WHERE tab = 'reference' AND item_name = ? "
                    "AND rarity = ?", (fix["now"], name, fix["was"])).rowcount
        return changed

    def set_variants(self, pairs) -> None:  # noqa: ANN001 -- Iterable[tuple[str, str]]
        """A dish and its special version, from the catalogue (D193): told apart by colour.

        The special version is the dish drawn again with something on it, and the picture
        model hardly sees it (青蔬蛋饼 was named 蛋饼 in every scan). Only these pairs:
        a colour rule for every look-alike pair renamed real 霍闪声核 to 隐雷声核."""
        variants: dict[str, set[str]] = {}
        for one, two in pairs:
            variants.setdefault(one, set()).add(two)
            variants.setdefault(two, set()).add(one)
        self._variants = {name: frozenset(v) for name, v in variants.items()}

    def set_reference_looks(self, look_of) -> None:  # noqa: ANN001 -- Callable[[str], ndarray | None]
        """How each catalogue picture looks (`describe`), for telling two tied ones apart (D201)."""
        self._reference_look = look_of

    def _by_look(self, query: np.ndarray, one: str, two: str) -> str | None:
        """Which of two tied catalogue pictures the tile looks like, if it plainly does."""
        a, b = self._reference_look(one), self._reference_look(two)
        if a is None or b is None:
            return None
        lead = float(query @ a) - float(query @ b)
        return one if lead >= LOOK_GAP else two if -lead >= LOOK_GAP else None

    def _by_colour(self, name: str | None, query: np.ndarray) -> str | None:
        """The special version (or the plain dish) `query` is by colour, else None."""
        mine = self._ref_colour.get(name or "")
        if mine is None:
            return None
        hits = [other for other in sorted(self._variants.get(name or "", ()))
                if other in self._ref_colour
                and float(self._ref_vector[name] @ self._ref_vector[other]) >= DRAWN_ALIKE
                and is_the_other(query, mine, self._ref_colour[other])]
        return hits[0] if len(hits) == 1 else None

    def _look_of(self, row) -> np.ndarray | None:  # noqa: ANN001 -- sqlite3.Row
        """`describe` of a NAMED screen-cut entry, from its saved crop; else None.

        Only named entries are ever candidates (require_named), and there are few,
        so the vector is computed from the crop on disk and cached rather than
        stored: `load` runs after every live view.
        """
        if row["item_name"] is None or row["tab"] == "reference":
            return None
        digest = row["icon_hash"]
        if digest not in self._look_cache:
            path = self.store.icon_dir / f"{digest}.webp"
            vec = None
            if path.exists():
                from PIL import Image

                with Image.open(path) as im:
                    vec = describe(np.asarray(im.convert("RGB"))).astype(np.float32)
            self._look_cache[digest] = vec
        return self._look_cache[digest]

    def _look_ok(self, query: np.ndarray) -> np.ndarray:
        """Per entry: may this entry name a crop that looks like `query`?"""
        if self._looks.shape[1] != query.size:
            return ~self._has_look
        return ~self._has_look | (self._looks @ query >= MIN_LOOK)

    def _colour_of(self, row) -> np.ndarray | None:  # noqa: ANN001 -- sqlite3.Row
        """The entry's hue signature; backfilled from its saved crop when missing."""
        if row["colour"] is not None:
            stored = np.frombuffer(row["colour"], dtype=np.float32)
            if stored.size == HUE_BINS:
                return stored
        if row["tab"] == "reference":
            return None
        path = self.store.icon_dir / f"{row['icon_hash']}.webp"
        if not path.exists():
            return None
        from PIL import Image

        with Image.open(path) as im:
            vec = hue_signature(np.asarray(im.convert("RGB")))
        self.store.conn.execute(
            "UPDATE gallery SET colour = ? WHERE icon_hash = ?",
            (vec.astype(np.float32).tobytes(), row["icon_hash"]),
        )
        self.store.conn.commit()
        return vec

    def _hue_cos(self, query: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Per entry: hue cosine to `query`, and whether either is too colourless to say."""
        mass = self._colours.sum(axis=1)
        norms = np.linalg.norm(self._colours, axis=1) * float(np.linalg.norm(query))
        cos = (self._colours @ query) / np.maximum(norms, 1e-12)
        return cos, np.minimum(mass, float(query.sum())) < MIN_HUE_MASS

    def _hue_ok(self, query: np.ndarray) -> np.ndarray:
        """Per entry: may this entry name `query`? Vectorised `same_hue`."""
        cos, colourless = self._hue_cos(query)
        return ~self._has_colour | colourless | (cos >= MIN_HUE)

    def _shut_out(self, query: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Per entry: a catalogue picture the hue check shuts out, and whether only just (D195)."""
        cos, colourless = self._hue_cos(query)
        is_ref = np.array([t == "reference" for t in self._tabs], dtype=bool)
        return self._has_colour & is_ref & ~colourless & (cos < MIN_HUE), cos >= NEAR_HUE

    @property
    def size(self) -> int:
        return len(self._hashes)

    # ------------------------------------------------------------------ write

    def add(
        self,
        icons: list[np.ndarray],
        hashes: list[str],
        rarities: list[int],
        names: list[str | None] | None = None,
        tab: str | None = None,
        vectors: np.ndarray | None = None,
        colours: list[np.ndarray] | None = None,
    ) -> int:
        """Embed and store crops that are not already present. Returns count added.

        `vectors`, aligned with `icons`, reuses embeddings the caller already has --
        a live view embeds its tiles once for `query` and hands them on here.
        `colours` (appearance.hue_signature of each crop) is given for crops from
        the game screen and left out for reference icons (see MIN_HUE).
        """
        key = self.encoder.info.key()
        known = {
            r["icon_hash"]
            for r in self.store.conn.execute(
                "SELECT icon_hash FROM gallery WHERE backbone = ?", (key,)
            ).fetchall()
        }

        todo = [i for i, h in enumerate(hashes) if h not in known]
        # Same crop can appear twice in one batch; embed it once.
        seen: set[str] = set()
        unique = []
        for i in todo:
            if hashes[i] not in seen:
                seen.add(hashes[i])
                unique.append(i)
        if not unique:
            return 0

        if vectors is not None:
            vectors = vectors[unique]
        else:
            vectors = self.encoder.embed([icons[i] for i in unique])
        now = datetime.now(UTC).isoformat(timespec="seconds")
        self.store.conn.executemany(
            """INSERT OR REPLACE INTO gallery
               (icon_hash, item_name, rarity, tab, backbone, embedding, created_at,
                colour)
               VALUES (?,?,?,?,?,?,?,?)""",
            [
                (
                    hashes[i],
                    (names[i] if names else None),
                    rarities[i],
                    tab,
                    key,
                    vectors[n].astype(np.float32).tobytes(),
                    now,
                    colours[i].astype(np.float32).tobytes() if colours is not None else None,
                )
                for n, i in enumerate(unique)
            ],
        )
        self.store.conn.commit()
        return len(unique)

    def refresh_reference(self, icons: list) -> tuple[int, int]:  # list[ReferenceIcon]
        """Bring the catalogue's icons in the gallery up to date: (added, dropped) (D179).

        Only what is new is embedded -- an entry already there keeps its vector and its
        date -- and an entry the catalogue no longer has is dropped (an English name of
        old, D42; an item renamed). Crops learned from scans are never touched. Cheap
        when nothing changed, so a scan can do it before it reads anything: a wiki
        update's new weapon is then known to the very next scan, not the one after.
        An item the catalogue never drew keeps its entry until the catalogue draws it (D249).
        """
        from .appearance import hue_signature
        from .reference import reference_key

        keys = [reference_key(i.image, i.name) for i in icons]
        wanted = set(keys)
        drawn = {i.name for i in icons}
        gone = [r[0] for r in self.store.conn.execute(
            "SELECT icon_hash, item_name FROM gallery WHERE tab = 'reference'")
            if r[0] not in wanted and not (r[0].startswith(NO_PICTURE) and r[1] not in drawn)]
        self.store.conn.executemany("DELETE FROM gallery WHERE icon_hash = ?",
                                    [(h,) for h in gone])
        self.store.conn.commit()
        have = {r[0] for r in self.store.conn.execute(
            "SELECT icon_hash FROM gallery WHERE tab = 'reference' AND backbone = ?",
            (self.encoder.info.key(),))}
        new = [n for n, k in enumerate(keys) if k not in have]
        added = self.add(
            [icons[n].image for n in new], [keys[n] for n in new],
            [icons[n].rarity for n in new], names=[icons[n].name for n in new], tab="reference",
            # the catalogue's own art: its hue matches the screen (D30, D42)
            colours=[hue_signature(icons[n].image) for n in new],
        ) if new else 0
        return added, len(gone)

    def name_item(self, icon_hash: str, item_name: str) -> None:
        """Attach a real item name, harvested from the detail panel during bootstrap.

        Not a name drawn the same as another's (D57, D200): such a picture never names a
        tile, so learning it only fills 识别 with pictures that cannot help."""
        if item_name in self._twins:
            return
        self.store.conn.execute(
            "UPDATE gallery SET item_name = ? WHERE icon_hash = ?", (item_name, icon_hash)
        )
        self.store.conn.commit()

    def name_crops(self, icon_hashes: list[str], item_name: str) -> int:
        """Name every still-unnamed crop of one item. Returns how many were named.

        The panel names the SELECTED tile's crop, which is framed a little
        differently (outline, scale); unselected sightings then scored only
        0.92-0.94 against it on `describe`, below MIN_LOOK. Naming every crop of
        the confirmed item gives each later sighting a like-for-like crop (D37).
        An entry that already has a name keeps it.

        Only crops that LOOK like the item are named (D92): like the crops among
        these already carrying `item_name` -- the one the panel just named, at
        least. "Every crop of the item" trusted the stitcher's idea of the item,
        and one mis-stitched slot handed a spear's name to a blade's 29 crops.
        With no such anchor nothing is named: a name is never spread blind. Nor is a name
        drawn the same as another's (D200, see `name_item`).
        """
        if not icon_hashes or item_name in self._twins:
            return 0
        rows = {
            r["icon_hash"]: r for r in self.store.conn.execute(
                "SELECT icon_hash, item_name, embedding FROM gallery WHERE icon_hash IN "
                f"({','.join('?' * len(icon_hashes))})", list(icon_hashes),
            )
        }

        def vec(r) -> np.ndarray | None:  # noqa: ANN001 -- sqlite3.Row
            if r is None or r["embedding"] is None:
                return None
            v = np.frombuffer(r["embedding"], dtype=np.float32)
            return v / (np.linalg.norm(v) or 1.0)

        anchors = [v for h in icon_hashes
                   if (r := rows.get(h)) is not None and r["item_name"] == item_name
                   and (v := vec(r)) is not None]
        if not anchors:
            return 0
        anchor = np.stack(anchors)
        like = [h for h in dict.fromkeys(icon_hashes)
                if (r := rows.get(h)) is not None and r["item_name"] is None
                and (v := vec(r)) is not None and float((anchor @ v).max()) >= SAME_ITEM_CROP]
        if not like:
            return 0
        cur = self.store.conn.executemany(
            "UPDATE gallery SET item_name = ? WHERE icon_hash = ? AND item_name IS NULL",
            [(item_name, h) for h in like],
        )
        self.store.conn.commit()
        return cur.rowcount

    # -------------------------------------------------------------- retrieval

    def query(
        self,
        icons: list[np.ndarray],
        rarities: list[int] | None = None,
        k: int = 2,
        require_named: bool = True,
        vectors: np.ndarray | None = None,
        colours: list[np.ndarray] | None = None,
        looks: list[np.ndarray] | None = None,
    ) -> list[Match | None]:
        """Identify each icon. Returns None where the gallery has no candidates.

        `require_named` restricts the search to entries that actually carry a name,
        and defaults to True because the gallery self-builds: every scan adds its
        own crops unnamed. Without this filter a later query matches those
        near-identical self-added copies (score ~1.0) instead of the named
        reference icon, and naming silently collapses to zero -- observed exactly
        that on a database holding 161 named references plus 75 self-added crops.

        Unnamed entries remain useful for de-duplication; they are simply not
        evidence of identity.

        `looks` (appearance.describe of each crop from the game screen) restricts
        panel-learned names to crops that look like the one they were learned on
        (MIN_LOOK). Reference icons are not gated by it.
        """
        if self.size == 0 or not icons:
            return [None] * len(icons)

        named_mask = np.array([n is not None for n in self._names], dtype=bool)
        if require_named and not named_mask.any():
            return [None] * len(icons)

        if vectors is None:
            vectors = self.encoder.embed(icons)
        results: list[Match | None] = []

        for i, vec in enumerate(vectors):
            if rarities is not None:
                # RARITY_ANY entries (reference icons whose name carries no tier
                # prefix) have no known rarity and must stay eligible, or gating
                # would silently exclude most of the reference gallery.
                mask = (self._rarities == rarities[i]) | (self._rarities == RARITY_ANY)
                if require_named:
                    mask &= named_mask
                if not mask.any():
                    # Nothing at this rarity; fall back to any named entry rather
                    # than refusing, and let the margin decide.
                    mask = named_mask if require_named else np.ones(self.size, dtype=bool)
            else:
                mask = named_mask if require_named else np.ones(self.size, dtype=bool)

            shut_out = just = None
            if colours is not None and self._has_colour.any():
                # Screen-cut entries must also match in hue (D30).
                shut_out, just = self._shut_out(colours[i])
                shut_out = shut_out & mask
                mask = mask & self._hue_ok(colours[i])
            if looks is not None and self._has_look.any():
                mask = mask & self._look_ok(looks[i])
            idx = np.flatnonzero(mask)
            if idx.size == 0:
                results.append(None)
                continue
            scores = self._matrix[idx] @ vec
            order = np.argsort(scores)[::-1]
            best = int(idx[order[0]])
            top = float(scores[order[0]])
            # The runner-up is the best entry naming something ELSE. Several
            # entries can name one item -- a reference icon in English plus live
            # crops named from the detail panel in Chinese (D24) -- and measuring
            # the margin against a copy of the winner would reject every match.
            second = 0.0
            for j in order[1:]:
                other = self._names[int(idx[j])]
                if other is None or other != self._names[best]:
                    second = float(scores[j])
                    break

            # Drawn the same as other items: never named from artwork (D57).
            shared = self._twins.get(self._names[best] or "")
            if shared:
                results.append(
                    Match(
                        icon_hash=self._hashes[best],
                        item_name=None,
                        rarity=int(self._rarities[best]),
                        score=top,
                        margin=top - second,
                        rivals=shared,
                    )
                )
                continue

            if shut_out is not None and shut_out.any():
                # A picture shut out on hue that is still clearly the better one: ask (D195).
                # By a hair, any clear lead; by more, a wide one.
                shut = np.flatnonzero(shut_out)
                shut_scores = self._matrix[shut] @ vec
                j = int(np.argmax(shut_scores))
                other = self._names[int(shut[j])]
                gap = MIN_MARGIN if just[int(shut[j])] else FAR_GAP
                if other != self._names[best] and float(shut_scores[j]) >= top + gap:
                    results.append(
                        Match(
                            icon_hash=self._hashes[best],
                            item_name=None,
                            rarity=int(self._rarities[best]),
                            score=top,
                            margin=top - second,
                            rivals=(other, self._names[best] or ""),
                            runner_up=self._names[best],
                        )
                    )
                    continue

            tied = next((int(idx[j]) for j in order[1:]
                         if self._names[int(idx[j])] != self._names[best]), None)
            if (looks is not None and self._reference_look is not None and tied is not None
                    and top - second < MIN_MARGIN
                    and self._tabs[best] == "reference" and self._tabs[tied] == "reference"
                    and float(self._matrix[best] @ self._matrix[tied]) < SAME_ART):
                # Two catalogue pictures tied on the picture model: the look decides (D201).
                picked = self._by_look(looks[i], self._names[best] or "", self._names[tied] or "")
                if picked is not None:
                    other = self._names[tied] if picked == self._names[best] else self._names[best]
                    results.append(Match(icon_hash=self._hashes[best], item_name=picked,
                                         rarity=int(self._rarities[best]), score=top,
                                         margin=MIN_MARGIN, runner_up=other))
                    continue

            rivals: tuple[str, ...] = ()
            second_idx = next(
                (int(idx[j]) for j in order[1:] if self._names[int(idx[j])] != self._names[best]),
                None,
            )
            same_art = (
                second_idx is not None
                and float(self._matrix[best] @ self._matrix[second_idx]) >= SAME_ART
            )
            if top - second < MIN_MARGIN and (second >= TWIN_SIMILARITY or same_art):
                # Several different names, each a near-duplicate of this crop.
                names: list[str] = []
                for j in order:
                    if float(scores[j]) < top - MIN_MARGIN:
                        break
                    name = self._names[int(idx[j])]
                    if name is not None and name not in names:
                        names.append(name)
                rivals = tuple(names)

            name = self._names[best]
            learned = self._tabs[best] != "reference"
            runner_up = self._names[second_idx] if second_idx is not None else None
            if colours is not None and not rivals and not (learned and top >= SAME_TILE):
                other = self._by_colour(name, colours[i])
                if other is not None:
                    # A dish and its special version, told apart by colour (D193).
                    name, runner_up, learned = other, name, False
            results.append(
                Match(
                    icon_hash=self._hashes[best],
                    item_name=name,
                    rarity=int(self._rarities[best]),
                    score=top,
                    margin=top - second,
                    rivals=rivals,
                    learned=learned,
                    runner_up=runner_up,
                )
            )
        return results
