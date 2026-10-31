# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""The gallery pack: a ready-made reference gallery that ships with the tool (D43).

User decision: other users should not have to build the reference gallery. What
recognition needs from the catalogue is not its images but what was computed from
them -- each entry's name, rarity, tab, DINOv2 embedding and hue vector. The pack
is exactly that, in one small file tracked in the repo. The icons themselves stay
unshipped (Kuro's assets, AGENTS.md); without them the pages show scanned crops
instead of catalogue art, and nothing else changes.

A pack is only valid for the embedding space it was built in: it records the
encoder key (model | preprocessing | size) and is refused under any other.

Build:  wuwa pack          (after tools/fetch_catalogue.py and wuwa seed)
Use:    automatic -- a gallery with no reference entries imports it (ensure_reference)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from ..store.db import Store

PACK_PATH = Path(__file__).resolve().parents[3] / "assets" / "gallery_pack.npz"
VERSION = 1


class PackMismatchError(RuntimeError):
    """The pack was built for another embedding space; its vectors are meaningless here."""


def export_pack(store: Store, path: Path = PACK_PATH) -> int:
    """Write the gallery's reference entries to a pack. Returns how many."""
    rows = store.conn.execute(
        "SELECT icon_hash, item_name, rarity, tab, backbone, embedding, colour FROM gallery "
        "WHERE tab = 'reference' AND embedding IS NOT NULL ORDER BY item_name"
    ).fetchall()
    if not rows:
        raise ValueError("no reference entries -- run tools/fetch_catalogue.py, then wuwa seed")
    tabs = _catalogue_tabs()
    backbones = {r["backbone"] for r in rows}
    if len(backbones) != 1:
        raise ValueError(f"reference entries from several encoders: {sorted(backbones)}")
    meta = {
        "version": VERSION,
        "backbone": backbones.pop(),
        "created": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": "wiki.kurobbs.com catalogue (tools/fetch_catalogue.py)",
        "keys": [r["icon_hash"] for r in rows],
        "names": [r["item_name"] for r in rows],
        "rarities": [int(r["rarity"]) for r in rows],
        "tabs": [tabs.get(r["item_name"]) for r in rows],
    }
    embeddings = np.stack([np.frombuffer(r["embedding"], dtype=np.float32) for r in rows])
    colours = np.stack([
        np.frombuffer(r["colour"], dtype=np.float32) if r["colour"] is not None
        else np.full(24, np.nan, dtype=np.float32)
        for r in rows
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path, meta=np.array(json.dumps(meta, ensure_ascii=False)),
        embeddings=embeddings.astype(np.float16), colours=colours,
    )
    return len(rows)


def read_pack(path: Path = PACK_PATH) -> tuple[dict, np.ndarray, np.ndarray]:
    with np.load(path) as data:
        meta = json.loads(str(data["meta"]))
        return meta, data["embeddings"].astype(np.float32), data["colours"]


def import_pack(store: Store, backbone: str, path: Path = PACK_PATH) -> int:
    """Replace the gallery's reference entries with the pack's. Returns how many."""
    meta, embeddings, colours = read_pack(path)
    if meta["backbone"] != backbone:
        raise PackMismatchError(
            f"pack built for {meta['backbone']}, this encoder is {backbone}"
        )
    now = datetime.now(UTC).isoformat(timespec="seconds")
    rows = []
    for i, key in enumerate(meta["keys"]):
        vec = embeddings[i]
        vec = vec / max(float(np.linalg.norm(vec)), 1e-12)  # float16 round-trip
        colour = None if np.isnan(colours[i]).any() else colours[i].astype(np.float32).tobytes()
        rows.append((key, meta["names"][i], meta["rarities"][i], "reference", meta["backbone"],
                     vec.astype(np.float32).tobytes(), now, colour))
    with store.conn:
        store.conn.execute("DELETE FROM gallery WHERE tab = 'reference'")
        store.conn.executemany(
            """INSERT OR REPLACE INTO gallery
               (icon_hash, item_name, rarity, tab, backbone, embedding, created_at, colour)
               VALUES (?,?,?,?,?,?,?,?)""",
            rows,
        )
    return len(rows)


def ensure_reference(store: Store, backbone: str, path: Path = PACK_PATH) -> int:
    """Import the shipped pack when the gallery has no reference entries yet."""
    has = store.conn.execute(
        "SELECT 1 FROM gallery WHERE tab = 'reference' AND backbone = ? LIMIT 1", (backbone,)
    ).fetchone()
    if has or not path.exists():
        return 0
    return import_pack(store, backbone, path)


def server_reference(store: Store, path: Path = PACK_PATH) -> int:
    """The catalogue's pictures for a server (D243). They are never sent to it and it has no
    recogniser to make them, so without the pack 更新 › 识别 has nothing to doubt a name against.
    A server that started from a scanner's database has them already, newer than these."""
    if not path.exists():
        return 0
    return ensure_reference(store, read_pack(path)[0]["backbone"], path)


def pack_names(path: Path = PACK_PATH) -> frozenset[str]:
    """Every name in the shipped pack (the snap list when no catalogue is downloaded)."""
    if not path.exists():
        return frozenset()
    meta, _, _ = read_pack(path)
    return frozenset(meta["names"])


def _catalogue_tabs() -> dict[str, str | None]:
    """Name -> bag tab, from the downloaded catalogue (empty without one)."""
    from .names import CATALOGUE_DIR

    index = CATALOGUE_DIR / "index.json"
    if not index.exists():
        return {}
    return {e["name"]: e.get("tab") for e in json.loads(index.read_text(encoding="utf-8"))}
