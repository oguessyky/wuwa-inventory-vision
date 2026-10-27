# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Reference icon gallery seeded from canonical item art.

`tools/fetch_catalogue.py` downloads canonical 256x256 item icons with names.
Seeding the gallery from those removes the need to hover every item in-game just
to learn what it is -- the original justification for driven mode (PLAN.md D6) and
the blocker on naming (D3/D17).

Two details make it work:

**Compositing.** Reference icons are artwork on transparency; our crops carry the
tile panel behind them. Compositing the reference onto a tile-like background
closes that domain gap: measured score median rose 0.858 -> 0.887 and coverage
(score > 0.7) 92% -> 95%.

**Tier -> rarity.** Item names carry a frequency-tier prefix (LF/MF/HF) that
corresponds to the in-game rarity colour. Cross-tabulated against our own measured
rarity across 75 scanned tiles, the mapping is 22/23 consistent:

        r2   r3   r4
    LF   7    0    0
    MF   1    8    0
    HF   0    0    7

This is mutual validation: a fan site's naming and our rarity-bar sampler are
independent, and they agree. It also makes rarity gating usable against reference
entries, which is what separates the LF/MF/HF variants the embedding confuses.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

#: The official Chinese catalogue (tools/fetch_catalogue.py, D42) when present,
#: else an older English icon set an early install may still have on disk (its
#: tool is gone since D133; nothing fetches that set any more).
LEGACY_DIR = Path("data/reference_icons")
INDEX_NAME = "index.json"


def reference_dir() -> Path:
    """Where the catalogue's pictures are -- asked each time, not once at start (D188).

    A home started before 从 Wiki 更新 fetched its catalogue, or a scanner before it took one from
    its home, had settled on `LEGACY_DIR` for good: the home's item pictures answered 404, and
    the scanner's check before a scan (D179) never saw the new items.
    """
    from .. import catalogue

    folder = Path(catalogue.CATALOGUE_DIR)
    return folder if (folder / INDEX_NAME).exists() else LEGACY_DIR

#: Median tile-panel colour, sampled from our own crops.
TILE_BACKGROUND = (55, 63, 70)

_TIER = re.compile(r"^(LF|MF|HF)\s+", re.IGNORECASE)

#: Frequency tier -> rarity, validated against measured rarity (see module docstring).
TIER_RARITY = {"LF": 2, "MF": 3, "HF": 4}

#: Rarity value meaning "unknown -- match against any rarity".
RARITY_ANY = 0


@dataclass(frozen=True, slots=True)
class ReferenceIcon:
    name: str
    rarity: int
    """From the tier prefix, or RARITY_ANY when the name carries none."""
    image: np.ndarray


def reference_key(image: np.ndarray, name: str) -> str:
    """Gallery key of a reference icon: its artwork AND its name.

    Keyed on the artwork alone, items the catalogue draws identically (撞金合剂 /
    划音合剂, four 溶剂) collapsed into one entry under whichever name came first,
    so the others could never be matched or flagged as twins -- all five wrong
    names measured on real crops were exactly these (D42).
    """
    from ..store.db import icon_hash

    return hashlib.sha256(f"{icon_hash(image)}|{name}".encode()).hexdigest()[:32]


def tier_rarity(name: str) -> int:
    """Infer rarity from a name's frequency-tier prefix."""
    match = _TIER.match(name)
    if not match:
        return RARITY_ANY
    return TIER_RARITY.get(match.group(1).upper(), RARITY_ANY)


def composite(rgba: Image.Image, background: tuple[int, int, int] = TILE_BACKGROUND) -> np.ndarray:
    """Flatten a transparent icon onto a tile-like background."""
    plate = Image.new("RGBA", rgba.size, (*background, 255))
    plate.alpha_composite(rgba.convert("RGBA"))
    return np.asarray(plate.convert("RGB"))


def load_reference_icons(
    directory: Path | str | None = None,
    background: tuple[int, int, int] = TILE_BACKGROUND,
) -> list[ReferenceIcon]:
    """Load downloaded reference icons, composited and ready to embed."""
    directory = Path(directory) if directory is not None else reference_dir()
    index_path = directory / INDEX_NAME
    if not index_path.exists():
        raise FileNotFoundError(
            f"{index_path} not found -- run: uv run python tools/fetch_catalogue.py"
        )

    from ..catalogue import fixed_rarity, read_item_fixes

    fixes = read_item_fixes()
    icons: list[ReferenceIcon] = []
    for entry in json.loads(index_path.read_text(encoding="utf-8")):
        path = directory / entry["file"]
        if not path.exists():
            continue
        with Image.open(path) as im:
            image = composite(im, background)
        name = entry["name"]
        # The catalogue states rarity (its `star`); the English set implies it.
        rarity = fixed_rarity(name, int(entry.get("rarity") or 0) or tier_rarity(name), fixes)
        icons.append(ReferenceIcon(name=name, rarity=rarity, image=image))
    return icons


def name_to_file(directory: Path | str | None = None) -> dict[str, str]:
    """Map item name -> reference icon filename.

    Used to show the canonical artwork on the page instead of the scanned crop.
    A scanned crop is a photograph of a tile: it carries the panel background, the
    wave pattern, and whatever the compositor blended behind it. The reference icon
    is the artwork itself, on transparency, at 256x256.

    One name ("Spliced String") appears twice, as .png and .webp of the same icon,
    so first-wins is safe here.
    """
    directory = Path(directory) if directory is not None else reference_dir()
    index_path = directory / INDEX_NAME
    if not index_path.exists():
        return {}
    mapping: dict[str, str] = {}
    for entry in json.loads(index_path.read_text(encoding="utf-8")):
        name, file = entry.get("name"), entry.get("file")
        if name and file and name not in mapping and (directory / file).exists():
            mapping[name] = file
    return mapping
