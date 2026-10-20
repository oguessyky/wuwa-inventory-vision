# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Who is carrying a weapon, read from the portrait on its tile (D61).

A 武器 tile wears the portrait of whoever has it equipped in its top-left corner.
That portrait is the only thing on screen that says which resonator holds which
weapon, and typing all of that in by hand is the job the weapon scan exists to
save.

What the portrait can and cannot do, measured on the 96 tiles of
train_dataset/wuwa_weapon_1..4:

* Telling a portrait from empty artwork is easy. Against the reference avatars
  every real portrait scored 0.59-0.87 and every empty corner 0.10-0.29 -- one
  clean gap, no overlap, so `PRESENT` sits in the middle of it.
* NAMING one is not. The reference avatars are the same artwork but framed wider,
  and at 50x50 px DINOv2's top match was right about a third of the time, with
  margins of 0.01-0.05. So a reference match NEVER names anybody: it only orders
  the shortlist the user picks from (D2 "identification requires a name").
* Recognising a face already seen is easy, but not with the encoder. A 40 px crop
  one pixel off, or drawn 6% larger on the selected tile, fell to 0.87 against
  itself while the closest different face scored 0.90: one portrait took several
  keys (D93, D95). A 12x12 thumbnail does not care about a pixel: the same face
  scores 0.935 or more, a different one 0.84 at most (`face_signature`).

So the gallery self-builds exactly like the item one: a new face is stored
unnamed, the user names it once on the 武器 page, and every later scan matches it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from ..store.db import Store, icon_hash
from .encoder import IconEncoder

#: The player character: one holder, whatever element the panel names (D72).
ROVER = "漂泊者"

#: Below this against every reference avatar, nobody is carrying it.
PRESENT = 0.45
#: The same face, drawn again, by `face_signature`. Measured on the 134 portraits
#: of a recorded 武器 run (3440x1440, selected tiles included): 0.935 and up for
#: the same face, 0.842 at most for a different one, nothing in between.
SAME_FACE = 0.89
#: A face is compared as a thumbnail this many pixels across (D95).
FACE_SIZE = 12
#: What `holder_face.backbone` says for a signature, so rows keyed by an older
#: comparison are never matched against.
FACE_KIND = f"thumbnail|{FACE_SIZE}x{FACE_SIZE}-rgb-centred|{FACE_SIZE * FACE_SIZE * 3}"
#: How many names to offer the user for an unnamed face.
SUGGESTIONS = 5
#: The reference avatars are the game's own head icons (the wiki's 头像 list,
#: D133), drawn a little wider than the tile's portrait. This is the part of one
#: that frames like the tile does. Measured on the 43 portraits a real database
#: held, each named by its user: the lowest scored 0.516 (PRESENT is 0.45), the
#: right name came first for 22 and was among the five offered for 31. The busts
#: these replaced, with the box tuned for them, gave 0.492, 8 and 16.
REFERENCE_BOX = (0.15, 0.10, 0.85, 0.80)
#: What the avatar's transparent background is composited onto: the tile's own
#: dark panel, so the reference and the crop share a background.
BACKDROP = (44, 48, 58, 255)


def face_signature(crop: np.ndarray) -> np.ndarray:
    """What makes two crops the same portrait: a small, centred, unit thumbnail.

    Coarse on purpose. The portrait is the same artwork every time, so all that
    differs between two sightings is a pixel of offset or a few percent of scale,
    and at 12x12 neither survives -- where the encoder, fed a 40 px crop, moved
    further for one pixel than it does between two different faces.
    """
    small = cv2.resize(
        np.ascontiguousarray(crop[..., :3]), (FACE_SIZE, FACE_SIZE), interpolation=cv2.INTER_AREA
    ).astype(np.float32).ravel()
    small -= small.mean()
    return small / max(float(np.linalg.norm(small)), 1e-6)


@dataclass(frozen=True, slots=True)
class HolderRead:
    """What one tile's corner says about who holds that weapon."""

    key: str | None = None
    """Content hash of the portrait; None when nobody is carrying it."""
    name: str | None = None
    """Only ever a name the user has given this face."""
    likeness: float = 0.0
    """Similarity to the closest reference avatar -- a presence score, not proof."""
    suggestions: tuple[str, ...] = ()
    """Reference names in similarity order, for the user's picker."""

    @property
    def equipped(self) -> bool:
        return self.key is not None


class Holders:
    """The portrait gallery: presence, the names the user has given, suggestions."""

    def __init__(
        self, store: Store, encoder: IconEncoder, catalogue_dir: Path | str = "data/catalogue"
    ) -> None:
        self.store = store
        self.encoder = encoder
        self.dir = Path(catalogue_dir)
        self._names: list[str] = []
        self._refs = np.zeros((0, 0), dtype=np.float32)
        self._faces: list[str] = []
        self._face_names: list[str | None] = []
        self._face_vectors = np.zeros((0, FACE_SIZE * FACE_SIZE * 3), dtype=np.float32)

    # ------------------------------------------------------------- loading

    @property
    def available(self) -> bool:
        """False without the downloaded avatars: then no portrait is ever read."""
        return len(self._names) > 0

    def load(self) -> int:
        """Embed the reference avatars and read back the faces already stored."""
        index = self.dir / "avatars.json"
        if index.exists():
            resonators = json.loads(index.read_text(encoding="utf-8")).get("resonators", {})
            images, names = [], []
            for name, file in resonators.items():
                path = self.dir / "avatars" / file
                if not path.exists():
                    continue
                images.append(self._reference(path))
                # the player character has two pictures (女漂泊者, 男漂泊者) and one name
                names.append(ROVER if ROVER in name else name)
            if images:
                self._refs = self.encoder.embed(images, mask_badges=False)
                self._names = names
        self._load_faces()
        return len(self._names)

    def _reference(self, path: Path) -> Image.Image:
        image = Image.open(path).convert("RGBA")
        image = Image.alpha_composite(Image.new("RGBA", image.size, BACKDROP), image)
        w, h = image.size
        x0, y0, x1, y1 = REFERENCE_BOX
        return image.convert("RGB").crop((int(w * x0), int(h * y0), int(w * x1), int(h * y1)))

    def _load_faces(self) -> None:
        rows = self.store.holder_faces(FACE_KIND)
        dim = FACE_SIZE * FACE_SIZE * 3
        self._faces = [r["key"] for r in rows]
        self._face_names = [r["name"] for r in rows]
        self._face_vectors = (
            np.stack([np.frombuffer(r["embedding"], dtype=np.float32).reshape(dim) for r in rows])
            if rows
            else np.zeros((0, dim), dtype=np.float32)
        )

    def name_face(self, key: str, read: str | None) -> str | None:
        """Name a portrait from the panel's "X装配中" (D64). Returns the name kept.

        The game's own words, so this is not a guess -- but OCR is, so the read is
        snapped onto the reference names and dropped if it lands nowhere near one.
        """
        if not key or not read:
            return None
        from .names import snap

        name = snap(read.strip(), self._names)
        if name not in self._names:
            return None
        if name.startswith(ROVER):
            # whichever of the eight forms the panel names, the holder is 漂泊者,
            # as the picker has it (D72, D103)
            name = ROVER
        known = self._face_names[self._faces.index(key)] if key in self._faces else None
        if known != name:
            self.store.set_holder_name(key, name)
            self._load_faces()
        return name

    # -------------------------------------------------------------- reading

    def read(self, crops: list[np.ndarray | None]) -> list[HolderRead]:
        """One read per crop; a None crop or an empty corner reads as "nobody"."""
        if not self.available:
            return [HolderRead() for _ in crops]
        wanted = [i for i, c in enumerate(crops) if c is not None and c.size]
        out = [HolderRead() for _ in crops]
        if not wanted:
            return out

        vectors = self.encoder.embed([crops[i] for i in wanted], mask_badges=False)
        likeness = vectors @ self._refs.T
        added = False
        for index, row in zip(wanted, likeness, strict=True):
            best = float(row.max())
            if best < PRESENT:
                continue  # no portrait: nobody is carrying this one
            crop = crops[index]
            assert crop is not None
            key, name = icon_hash(crop), None
            vector = face_signature(crop)
            if len(self._face_vectors):
                sims = self._face_vectors @ vector
                near = int(np.argmax(sims))
                if float(sims[near]) >= SAME_FACE:
                    key, name = self._faces[near], self._face_names[near]
            order = np.argsort(-row)[:SUGGESTIONS]
            suggestions = tuple(dict.fromkeys(self._names[i] for i in order))
            if key not in self._faces:
                self.store.add_holder_face(
                    key, FACE_KIND, vector.astype(np.float32).tobytes(), suggestions
                )
                # Known at once: the next crop in this same batch may be this face.
                self._faces.append(key)
                self._face_names.append(None)
                self._face_vectors = np.vstack([self._face_vectors, vector[None]])
                added = True
            out[index] = HolderRead(
                key=key, name=name, likeness=best, suggestions=suggestions
            )
        if added:
            self._load_faces()
        return out
