# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""What the scanners have learned, and where the catalogue disagrees (D166).

Every picture saved from the game under a name is matched exactly by every scan after it, so
a wrong name, once learned, sticks: on 2026-10-12 a panel credited to the sword beside it filed
永远的启明星's picture as 云琅 three times. The catalogue's own pictures are an independent
witness. Where they are SURE a learned picture is another item -- the best of them names
something else, by at least the margin a weapon's panel is refused at (PICTURE_SURE) -- the
picture is flagged for the 更新 › 识别 page, which is where a person puts it right -- or says
the name is right after all (D167), and the flag stays down while the name stays the same.

The embeddings weigh the whole tile against a clean catalogue picture, so a face or a glow in it
can raise a doubt on a right name. A doubt stands only if the real pictures agree with it (D248).

Plain numpy over the stored embeddings: no encoder, no torch, so a home that has no recogniser
(D145) can show it too.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from ..store.db import Store
from .appearance import HUE_BINS, LOOK_GAP, describe
from .reference import RARITY_ANY, composite, name_to_file

#: How sure the catalogue must be that a learned picture is another item (D165, D166).
SURE = 0.05
#: How much nearer its own catalogue picture a doubted picture must be on the stored hue
#: signatures, on a machine with no catalogue pictures to compare (D248). Colour is the weaker
#: witness: 305 of 1,712,722 simulated slips reach this, and the one of 2026-10-12 is at -0.008.
COLOURS_SAY = 0.5


@dataclass(frozen=True, slots=True)
class Crop:
    """One picture saved from the game, and what the catalogue makes of it."""

    hash: str
    name: str
    rarity: int
    tab: str | None
    created_at: str
    doubt: str | None = None
    """The item the catalogue is sure this is, when that is not `name`."""
    margin: float = 0.0
    confirmed: bool = False
    """A person said `name` is right (D167): the catalogue's doubt is not shown."""


def learned(store: Store, known: Collection[str] | None = None,
            directory: Path | None = None) -> list[Crop]:
    """Every named picture saved from the game, with the catalogue's doubts beside it.

    `known`: the names the downloaded catalogue has; None when there is none yet. The pictures
    can be older than the names (D243), and an item with no picture of its own would lose to
    whatever looks most like it, so it is not doubted. A name no catalogue has heard of is.
    `directory`: where the catalogue's pictures are, to check a doubt against (D248)."""
    rows = store.conn.execute(
        "SELECT icon_hash, item_name, rarity, tab, backbone, embedding, created_at, colour "
        "FROM gallery WHERE item_name IS NOT NULL AND (tab IS NULL OR tab != 'reference')"
    ).fetchall()
    refs = store.conn.execute(
        "SELECT item_name, rarity, backbone, embedding, colour FROM gallery "
        "WHERE tab = 'reference' AND item_name IS NOT NULL AND embedding IS NOT NULL"
    ).fetchall()
    confirmed = store.confirmed_crops()
    drawn = {r[0] for r in refs}
    witness = _Pictures(store.icon_dir, directory, {r[0]: r[4] for r in refs})
    by_backbone: dict[str, tuple[list[str], np.ndarray, np.ndarray]] = {}
    for backbone in {r[2] for r in refs}:
        mine = [r for r in refs if r[2] == backbone]
        matrix = np.stack([_unit(r[3]) for r in mine]) if mine else np.zeros((0, 0), np.float32)
        by_backbone[backbone] = ([r[0] for r in mine], np.array([r[1] for r in mine]), matrix)
    out = []
    for digest, name, rarity, tab, backbone, blob, created, colour in rows:
        doubt, margin = None, 0.0
        sure = confirmed.get(digest) == name
        weighed = name in drawn or (known is not None and name not in known)
        if blob is not None and backbone in by_backbone and not sure and weighed:
            doubt, margin = _verdict(name, rarity, _unit(blob), *by_backbone[backbone])
        if doubt and name in drawn and witness.clears(digest, colour, name, doubt):
            doubt, margin = None, 0.0
        out.append(Crop(digest, name, rarity, tab, created, doubt, margin, sure))
    return out


def _unit(blob: bytes) -> np.ndarray:
    v = np.frombuffer(blob, dtype=np.float32)
    return v / max(float(np.linalg.norm(v)), 1e-12)


class _Pictures:
    """The real pictures behind a doubt, read only for the few pictures that are doubted (D248)."""

    def __init__(self, crops: Path, directory: Path | None, colours: dict[str, bytes | None]):
        self.crops = crops
        self.directory = directory
        self.colours = colours
        self._files: dict[str, str] | None = None
        self._looks: dict[str, np.ndarray | None] = {}

    def clears(self, digest: str, colour: bytes | None, name: str, doubt: str) -> bool:
        """Do the pictures say this tile is `name`, not `doubt`? When they can be read, they
        decide. Nothing to compare keeps the doubt: it is a question a person answers."""
        tile = self._tile(digest)
        own, other = self._drawn(name), self._drawn(doubt)
        if tile is not None and own is not None and other is not None:
            return float(tile @ own) - float(tile @ other) >= LOOK_GAP
        mine, theirs = _hue(colour), _hue(self.colours.get(name))
        doubted = _hue(self.colours.get(doubt))
        if mine is None or theirs is None or doubted is None:
            return False
        return float(mine @ theirs) - float(mine @ doubted) >= COLOURS_SAY

    def _tile(self, digest: str) -> np.ndarray | None:
        try:
            with Image.open(self.crops / f"{digest}.webp") as im:
                return describe(np.asarray(im.convert("RGB")))
        except OSError:
            return None

    def _drawn(self, name: str) -> np.ndarray | None:
        if name not in self._looks:
            if self._files is None:
                self._files = name_to_file(self.directory) if self.directory else {}
            file = self._files.get(name)
            self._looks[name] = None
            if file is not None:
                try:
                    with Image.open(self.directory / file) as im:
                        self._looks[name] = describe(composite(im))
                except OSError:
                    pass                          # a picture that cannot be read says nothing
        return self._looks[name]


def _hue(blob: bytes | None) -> np.ndarray | None:
    """A stored hue signature as a unit vector; None when it is missing or has no colour."""
    if blob is None:
        return None
    vec = np.frombuffer(blob, dtype=np.float32)
    norm = float(np.linalg.norm(vec))
    return vec / norm if vec.size == HUE_BINS and norm > 0 else None


def _verdict(name: str, rarity: int, vec: np.ndarray, names: list[str], rarities: np.ndarray,
             matrix: np.ndarray) -> tuple[str | None, float]:
    """The other item the catalogue is sure this picture is, and by how much; else (None, 0).

    A rarity can be wrong on either side, misread off the tile or the wiki's (D199), so its gate
    is for other items only: a picture whose best match of all is its own is not doubted (D247)."""
    if not len(names) or matrix.shape[1] != vec.shape[0]:
        return None, 0.0
    similar = matrix @ vec
    if names[int(np.argmax(similar))] == name:
        return None, 0.0
    allowed = (rarities == rarity) | (rarities == RARITY_ANY)
    if not allowed.any():
        allowed = np.ones(len(names), dtype=bool)
    scores = np.where(allowed, similar, -np.inf)
    best = int(np.argmax(scores))
    top = names[best]
    if top == name:
        return None, 0.0
    # the margin is to the best picture of any OTHER item, as the gallery measures it
    rest = [float(s) for n, s in zip(names, scores, strict=True) if n != top and np.isfinite(s)]
    margin = float(scores[best]) - (max(rest) if rest else 0.0)
    return (top, margin) if margin >= SURE else (None, 0.0)
