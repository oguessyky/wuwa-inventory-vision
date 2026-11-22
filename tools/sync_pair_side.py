# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""One side of a sync pair, run inside one version's own source (`sync_pairs.py` starts it).

    python sync_pair_side.py SRC seed-scanner DB
    python sync_pair_side.py SRC seed-server DB
    python sync_pair_side.py SRC serve DB PORT KEY      the server, on 127.0.0.1 only
    python sync_pair_side.py SRC sync DB URL KEY DIR     push, then pull; says how each went
    python sync_pair_side.py SRC dump DB                 what this copy holds, as JSON

SRC is that version's `src/`, put first on the path, so this side runs that version's code and
nothing of today's. Only the store's own methods and plain SQL that every version since 1.0.2
understands are used: a method a version does not have is skipped, and a table it does not have
is reported as missing, not as empty.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])

import numpy as np  # noqa: E402

from wuwa_vision.store.db import Observation, Store  # noqa: E402

A, B, F, D, G = "a" * 32, "b" * 32, "f" * 32, "d" * 32, "e" * 32


def _columns(store: Store, table: str) -> set[str]:
    return {r[1] for r in store.conn.execute(f"PRAGMA table_info({table})")}


def _gallery(store: Store, digest: str, name: str | None) -> None:
    row = {"icon_hash": digest, "item_name": name, "rarity": 3, "tab": "素材",
           "backbone": "dinov2", "embedding": np.arange(4, dtype=np.float32).tobytes(),
           "created_at": "2026-10-01T00:00:00+00:00", "colour": None}
    row = {k: v for k, v in row.items() if k in _columns(store, "gallery")}
    store.conn.execute(f"INSERT INTO gallery ({', '.join(row)}) VALUES "  # noqa: S608
                       f"({', '.join('?' * len(row))})", list(row.values()))
    store.conn.commit()
    store.save_icon(digest, np.full((8, 8, 3), int(digest[0], 16) * 16, dtype=np.uint8))


def _face(store: Store, key: str, name: str) -> None:
    store.add_holder_face(key, "dinov2", b"\x01\x02", (name,))
    if "name" in _columns(store, "holder_face"):
        store.conn.execute("UPDATE holder_face SET name = ? WHERE key = ?", (name, key))
        store.conn.commit()
    store.save_icon(key, np.zeros((8, 8, 3), dtype=np.uint8))


def _scan(store: Store, tab: str, when: str, tiles: list[tuple[str, str | None, int]],
          holder: str | None = None) -> None:
    scan_id = store.begin_scan("live", tab, len(tiles))
    store.conn.execute("UPDATE scan SET started_at = ? WHERE id = ?", (when, scan_id))
    rows = []
    for i, (digest, name, count) in enumerate(tiles):
        extra = {"holder_key": holder} if "holder_key" in Observation.__dataclass_fields__ else {}
        rows.append(Observation(frame="f1", row=0, col=i, icon_hash=digest, rarity=3,
                                rarity_conf=1.0, count=count, count_conf=0.9, item_name=name,
                                item_key=f"k{i}", **extra))
    store.add_observations(scan_id, rows)
    store.finish_scan(scan_id, 1, len(tiles), True)


def seed_scanner(db: Path) -> None:
    """What a scanner sends: two scans and everything they taught."""
    store = Store(db)
    _gallery(store, A, "低频核")
    _gallery(store, B, None)
    _face(store, F, "今汐")
    store.learn_weapon_kind("千古洑流", "迅刀")
    store.add_wallet(1000, 20, 0.9)
    store.add_alias("低频合", "低频核")
    _scan(store, "素材", "2026-10-02T10:00:00+00:00", [(A, "低频核", 12), (B, None, 3)])
    _scan(store, "武器", "2026-10-02T10:05:00+00:00", [(A, "低频核", 1)], holder=F)
    if hasattr(store, "save_character_read"):
        store.save_character_read("今汐", "attributes", {"level": 90})
    store.close()


def seed_server(db: Path) -> None:
    """What a server holds that the scanner lacks: another machine's learning, the user's own
    corrections and pull import."""
    store = Store(db)
    _gallery(store, D, "服务器里的")
    _gallery(store, G, "改过名的")
    _face(store, "9" * 32, "长离")
    store.learn_weapon_kind("赫奕流明", "长刃")
    store.add_alias("错的名字", "对的名字")
    if hasattr(store, "set_pulls"):
        store.set_pulls({"playerId": "0", "pulls": []})
    store.close()


def serve(db: Path, port: int, key: str) -> None:
    import uvicorn

    from wuwa_vision.web.app import create_app

    uvicorn.run(create_app(db, home_key=key), host="127.0.0.1", port=port, log_level="warning")


def run_sync(db: Path, url: str, key: str, catalogue: Path) -> dict:
    from wuwa_vision import sync

    store = Store(db)
    said: dict[str, str] = {}
    home = sync.Home(url, key)
    for way in ("push", "pull"):
        try:
            if way == "push":
                home.push(store)
            else:
                home.pull(store, catalogue)
            said[way] = "ok"
        except Exception as exc:  # noqa: BLE001 -- every failure is the pair's result
            said[way] = f"{type(exc).__name__}: {exc}"
    store.close()
    return said


def dump(db: Path) -> dict:
    """What this copy holds, in the same shape on every version. A table this version does not
    have is left out: `losses` reads that as "nowhere to keep them"."""
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    out: dict = {}
    if "scan" in tables:
        out["scans"] = {r["uid"]: r["n"] for r in conn.execute(
            "SELECT s.uid AS uid, COUNT(o.id) AS n FROM scan s LEFT JOIN observation o "
            "ON o.scan_id = s.id GROUP BY s.id")}
    if "gallery" in tables:
        out["gallery"] = {r["icon_hash"]: r["item_name"] for r in conn.execute(
            "SELECT icon_hash, item_name FROM gallery WHERE tab IS NULL OR tab != 'reference'")}
    if "holder_face" in tables:
        named = "name" in {r[1] for r in conn.execute("PRAGMA table_info(holder_face)")}
        out["faces"] = {r[0]: (r[1] if named else None) for r in conn.execute(
            "SELECT key, " + ("name" if named else "NULL") + " FROM holder_face")}
    if "weapon_kind" in tables:
        out["weapon_kinds"] = {r[0]: r[1] for r in conn.execute(
            "SELECT name, kind FROM weapon_kind")}
    if "wallet" in tables:
        out["wallet"] = sorted(r[0] for r in conn.execute("SELECT shells FROM wallet"))
    alias = next((t for t in ("alias", "aliases", "name_alias") if t in tables), None)
    if alias is not None:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({alias})")]
        wrong, right = cols[1:3] if cols[0] == "id" else cols[:2]
        out["aliases"] = {r[0]: r[1] for r in conn.execute(
            f"SELECT {wrong}, {right} FROM {alias}")}  # noqa: S608
    if "character_reads" in tables:
        out["character_reads"] = sorted(f"{r[0]}/{r[1]}" for r in conn.execute(
            "SELECT resonator, screen FROM character_reads"))
    if "pull_import" in tables:
        out["pulls"] = [r[0] for r in conn.execute("SELECT data FROM pull_import")]
    icons = db.parent / "icons"
    out["icons"] = sorted(p.stem for p in icons.glob("*.webp")) if icons.is_dir() else []
    conn.close()
    return out


def main(argv: list[str]) -> None:
    command, db = argv[2], Path(argv[3])
    if command == "seed-scanner":
        seed_scanner(db)
    elif command == "seed-server":
        seed_server(db)
    elif command == "serve":
        serve(db, int(argv[4]), argv[5])
    elif command == "sync":
        print(json.dumps(run_sync(db, argv[4], argv[5], Path(argv[6]))))
    elif command == "dump":
        print(json.dumps(dump(db), ensure_ascii=False))
    else:
        raise SystemExit(f"unknown command {command}")


if __name__ == "__main__":
    main(sys.argv)
