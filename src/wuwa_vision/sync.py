# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""A scanner and its home (PLAN.md D129, D145).

One machine can be the whole app, and by default is. Or the dashboard lives on a
box that is always on -- the *home* -- and the machine with the game is a
*scanner*: before a scan it fetches what the home has learned, it scans against
its own copy, and when the scan is finished it hands the scan over in one upload.
A network drop in the middle of a scan costs nothing; a scan that could not be
handed over is kept and sent the next time.

What crosses, and what never does:

* scanner -> home: finished scans (rows), the tile and portrait crops they point
  at, and what the scans taught (gallery entries, portraits, weapon kinds, the
  wallet). Tile crops are cut from inside the grid and never hold the UID
  (`Store.save_icon`); **no frame is ever sent** (hard constraint 4).
* home -> scanner: the same learned things as the home now has them (names given
  on a phone, another scanner's icons), the pull history, and the catalogue.

Nothing is copied as a file. Every table is merged row by row, by the row's own
key -- an icon by its content hash, a scan by its `uid` -- so two scanners cannot
overwrite each other, and sending the same thing twice adds nothing.

**The home is the truth for whatever it holds.** A scanner's word counts for a
row the home has never seen; for a row the home has, the home's value stands,
including "no name" (somebody may have taken a wrong name away there). And a row
the home *had* and has no longer was removed there -- a phantom tile somebody
dismissed -- so the scanner removes its own, instead of sending it back
(`sync_seen` is how it tells "removed there" from "new here").

This module is the whole of it and knows nothing of HTTP beyond the small client
at the bottom: `web/app.py` and `cli.py` are thin callers.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import hmac
import io
import ipaddress
import json
import re
import secrets
import shutil
import socket
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import deque
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path

from .store.db import SYNC_EPOCH, Store

#: What both ends must agree on to talk at all. Raised when the bundle changes shape.
PROTOCOL = 1
#: An upload larger than this is refused before it is read (a session's scans are
#: a few megabytes; a first upload of years of crops, some tens).
MAX_BUNDLE_BYTES = 256_000_000
MAX_JSON_BYTES = 64_000_000
MAX_ICON_BYTES = 2_000_000
#: A crop's name: the first 32 hex digits of a SHA-256 (`store.db.icon_hash`).
_DIGEST = re.compile(r"^[0-9a-f]{32}$")
_UID = re.compile(r"^[0-9a-f]{32}$")
_OBS = ("frame", "row", "col", "icon_hash", "rarity", "rarity_conf", "count", "count_conf",
        "item_name", "needs_review", "item_key", "rivals", "level", "holder_key")
_SCAN = ("uid", "started_at", "source", "tab_label", "header_total", "frame_count",
         "tile_count", "complete", "app_version")
#   `app_version` (D197): a home before 1.1.1 reads only the fields it knows, and a scanner
#   before it sends none -- NULL here, "1.1.0 or older" on the pages.
_GALLERY = ("icon_hash", "item_name", "rarity", "tab", "backbone", "embedding", "created_at",
            "colour")
_FACE = ("key", "name", "backbone", "embedding", "created_at", "named_at", "suggestions")
#: Gallery rows that are the catalogue, not a scan: every machine builds its own
#: from the shipped pack (`seed`), so they are never sent.
_REFERENCE = "reference"
HOME_KEY_FILE, HOME_FILE = "home.key", "home.json"


class SyncError(Exception):
    """Something the other end said no to, or that could not be read. Its text is for the user."""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _b64(blob: bytes | None) -> str | None:
    return base64.b64encode(blob).decode("ascii") if blob is not None else None


def _blob(text: str | None) -> bytes | None:
    return base64.b64decode(text) if text is not None else None


def _digests(values) -> list[str]:  # noqa: ANN001 -- any iterable of maybe-strings
    return sorted({v for v in values if isinstance(v, str) and _DIGEST.match(v)})


# ---------------------------------------------------------------- the scanner's side


def unsent_scans(store: Store) -> list[sqlite3.Row]:
    """Finished scans the home has not taken yet, oldest first. A scan that never
    learned which tab it was looking at shows nowhere, and is not worth sending."""
    return store.conn.execute(
        "SELECT * FROM scan WHERE synced_at IS NULL AND tab_label IS NOT NULL ORDER BY id"
    ).fetchall()


def _learned(store: Store) -> tuple[dict[str, str | None], dict[str, str | None]]:
    gallery = {r["icon_hash"]: r["item_name"] for r in store.conn.execute(
        "SELECT icon_hash, item_name FROM gallery WHERE tab IS NULL OR tab != ?", (_REFERENCE,))}
    faces = {r["key"]: r["name"] for r in store.conn.execute("SELECT key, name FROM holder_face")}
    return gallery, faces


def offer(store: Store, scans: list[sqlite3.Row] | None = None, everything: bool = True) -> dict:
    """What this scanner has that a home might lack: names only, nothing heavy.

    `scans`: only these (one part of a push, D171), with -- unless `everything` -- only what
    they taught: the learned rows their crops are. The last part offers all the rest."""
    scans = unsent_scans(store) if scans is None else scans
    crops: set[str] = set()
    for scan in scans:
        for row in store.conn.execute(
            "SELECT icon_hash, holder_key FROM observation WHERE scan_id = ?", (scan["id"],)
        ):
            crops.update(v for v in (row["icon_hash"], row["holder_key"]) if v)
    gallery, faces = _learned(store)
    if not everything:
        gallery = {k: v for k, v in gallery.items() if k in crops}
        faces = {k: v for k, v in faces.items() if k in crops}
    have = {p.stem for p in store.icon_dir.glob("*.webp")}
    return {
        "protocol": PROTOCOL, "epoch": store.sync_epoch(),
        "scans": [s["uid"] for s in scans],
        "gallery": sorted(gallery), "faces": sorted(faces),
        "icons": _digests((crops | set(gallery) | set(faces)) & have),
    }


def bundle(store: Store, need: dict) -> bytes:
    """One upload: the scans the home asked for, what they taught, and their crops."""
    wanted = set(need.get("scans") or [])
    scans = []
    for scan in unsent_scans(store):
        if scan["uid"] not in wanted:
            continue
        rows = store.conn.execute(
            f"SELECT {', '.join(_OBS)} FROM observation WHERE scan_id = ? ORDER BY id",  # noqa: S608
            (scan["id"],)).fetchall()
        scans.append({**{k: scan[k] for k in _SCAN}, "observations": [list(r) for r in rows]})

    def rows_of(table: str, columns: tuple[str, ...], key: str, asked: list[str]) -> list[dict]:
        out = []
        for name in _digests(asked):
            row = store.conn.execute(
                f"SELECT {', '.join(columns)} FROM {table} WHERE {key} = ?", (name,)).fetchone()  # noqa: S608
            if row is not None and (table != "gallery" or row["tab"] != _REFERENCE):
                out.append({k: (_b64(row[k]) if k in ("embedding", "colour") else row[k])
                            for k in columns})
        return out

    first = min((s["started_at"] for s in scans), default=None)
    wallet = [dict(r) for r in store.conn.execute(
        "SELECT read_at, shells, astrite, confidence FROM wallet WHERE read_at >= ? ORDER BY id",
        (first,))] if first else []
    said = {
        "protocol": PROTOCOL, "epoch": store.sync_epoch(), "scans": scans,
        "gallery": rows_of("gallery", _GALLERY, "icon_hash", need.get("gallery") or []),
        "faces": rows_of("holder_face", _FACE, "key", need.get("faces") or []),
        "weapon_kinds": store.weapon_kinds(), "aliases": store.aliases(), "wallet": wallet,
    }
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as z:
        z.writestr("bundle.json", json.dumps(said, ensure_ascii=False))
        for digest in _digests(need.get("icons") or []):
            path = store.icon_dir / f"{digest}.webp"
            if path.is_file():
                z.write(path, f"icons/{digest}.webp")
    return out.getvalue()


def mark_sent(store: Store, uids: list[str]) -> int:
    """The home has these (it took them now, or already had them)."""
    with store.conn:
        return sum(store.conn.execute(
            "UPDATE scan SET synced_at = ? WHERE uid = ? AND synced_at IS NULL", (_now(), uid)
        ).rowcount for uid in uids)


def mark_seen(store: Store, gallery: list[str] | set[str], faces: list[str] | set[str]) -> None:
    """The home holds these learned rows: from now on, their absence there means removed."""
    with store.conn:
        store.conn.executemany(
            "INSERT OR IGNORE INTO sync_seen (kind, key) VALUES (?, ?)",
            [("gallery", k) for k in gallery] + [("face", k) for k in faces])


def have(store: Store) -> dict:
    """What this scanner already knows, so the home sends only the difference."""
    gallery, faces = _learned(store)
    return {"protocol": PROTOCOL, "epoch": store.sync_epoch(), "gallery": gallery, "faces": faces}


def apply_state(store: Store, state: dict) -> dict:
    """Take what the home knows into this scanner's copy. The home's word stands
    for every row it has; rows only this scanner has are left for the next upload."""
    took = {"gallery": 0, "names": 0, "faces": 0, "aliases": 0, "weapon_kinds": 0, "pulls": 0,
            "removed": 0}
    gone = state.get("gone") or {}
    with store.conn:
        # What the home had and has no longer, it removed. What it never had is new
        # here and stays, to be offered with the next upload.
        tables = (("gallery", "gallery", "icon_hash"), ("face", "holder_face", "key"))
        for kind, table, key in tables:
            for name in _digests(gone.get(kind) or []):
                if not store.conn.execute(
                    "DELETE FROM sync_seen WHERE kind = ? AND key = ?", (kind, name)
                ).rowcount:
                    continue
                took["removed"] += store.conn.execute(
                    f"DELETE FROM {table} WHERE {key} = ?"  # noqa: S608
                    + (" AND (tab IS NULL OR tab != 'reference')" if kind == "gallery" else ""),
                    (name,)).rowcount
        for row in state.get("gallery") or []:
            if not _DIGEST.match(str(row.get("icon_hash"))) or row.get("tab") == _REFERENCE:
                continue
            took["gallery"] += store.conn.execute(
                f"INSERT OR IGNORE INTO gallery ({', '.join(_GALLERY)}) "  # noqa: S608
                f"VALUES ({', '.join('?' * len(_GALLERY))})",
                [(_blob(row.get(k)) if k in ("embedding", "colour") else row.get(k))
                 for k in _GALLERY]).rowcount
        for digest, name in (state.get("names") or {}).items():
            took["names"] += store.conn.execute(
                "UPDATE gallery SET item_name = ? WHERE icon_hash = ? AND item_name IS NOT ? "
                "AND (tab IS NULL OR tab != ?)", (name, digest, name, _REFERENCE)).rowcount
        for row in state.get("faces") or []:
            if not _DIGEST.match(str(row.get("key"))):
                continue
            took["faces"] += store.conn.execute(
                f"INSERT OR IGNORE INTO holder_face ({', '.join(_FACE)}) "  # noqa: S608
                f"VALUES ({', '.join('?' * len(_FACE))})",
                [(_blob(row.get(k)) if k == "embedding" else row.get(k)) for k in _FACE]).rowcount
        for key, name in (state.get("face_names") or {}).items():
            took["names"] += store.conn.execute(
                "UPDATE holder_face SET name = ?, named_at = ? WHERE key = ? AND name IS NOT ?",
                (name, _now(), key, name)).rowcount
        for name, kind in (state.get("weapon_kinds") or {}).items():
            took["weapon_kinds"] += store.conn.execute(
                "INSERT INTO weapon_kind(name, kind, seen_at) VALUES (?,?,?) "
                "ON CONFLICT(name) DO UPDATE SET kind = excluded.kind "
                "WHERE weapon_kind.kind != excluded.kind",
                (name, kind, _now())).rowcount
        pulls = state.get("pulls")
        mine = store.conn.execute(
            "SELECT imported_at FROM pull_import ORDER BY id DESC LIMIT 1").fetchone()
        if pulls and (mine is None or mine["imported_at"] != pulls.get("imported_at")):
            store.conn.execute("DELETE FROM pull_import")
            store.conn.execute("INSERT INTO pull_import (imported_at, data) VALUES (?, ?)",
                               (pulls["imported_at"],
                                json.dumps(pulls["data"], ensure_ascii=False)))
            took["pulls"] = 1
    # a correction rewrites what is already stored, so it goes through the store's own door
    known = store.aliases()
    for wrong, right in (state.get("aliases") or {}).items():
        if known.get(wrong) != right:
            store.add_alias(wrong, right)
            took["aliases"] += 1
    return took


def start_over(store: Store, epoch: int) -> Path:
    """The home was wiped (清空扫描数据) since this scanner last spoke to it: what this
    copy learned belongs to a past that was thrown away. Set aside, then forgotten,
    the same way the home did it -- or the next upload would bring it all back."""
    folder = store.path.parent / "backups" / datetime.now().strftime("%Y%m%d-%H%M%S-home-wiped")
    store.backup_to(folder / store.path.name)
    icons = store.icon_dir
    if any(icons.iterdir()):
        shutil.move(str(icons), str(folder / "icons"))
    store.wipe_scans()
    store.set_setting(SYNC_EPOCH, str(epoch))
    return folder


# ------------------------------------------------------------------- the home's side


def need(store: Store, offered: dict) -> dict:
    """Of what a scanner offers, what this home does not have yet."""
    _same_protocol(offered)
    if int(offered.get("epoch") or 0) != store.sync_epoch():
        raise SyncError("扫描数据在主机上被清空过；先同步（pull）再上传。")
    known_scans = {r["uid"] for r in store.conn.execute("SELECT uid FROM scan")}
    gallery, faces = _learned(store)
    on_disk = {p.stem for p in store.icon_dir.glob("*.webp")}
    return {
        "protocol": PROTOCOL,
        "scans": [u for u in offered.get("scans") or []
                  if _UID.match(str(u)) and u not in known_scans],
        "known": [u for u in offered.get("scans") or [] if u in known_scans],
        "gallery": [d for d in _digests(offered.get("gallery") or []) if d not in gallery],
        "faces": [d for d in _digests(offered.get("faces") or []) if d not in faces],
        "icons": [d for d in _digests(offered.get("icons") or []) if d not in on_disk],
    }


def _same_protocol(said: dict) -> None:
    if said.get("protocol") != PROTOCOL:
        raise SyncError(f"两边的版本不一样（这边是 {PROTOCOL}，对面是 {said.get('protocol')}）；"
                        "把扫描端和主机更新到同一个版本。")


def _insert_scan(conn: sqlite3.Connection, scan: dict) -> int:
    """Insert a scan so that ids still run in the order the scans were made.

    Everything that asks "which is the newest" asks by id (`inventory`, `weapons`),
    and on one machine that is the order of time. A home hears from more than one:
    a scan made on the laptop yesterday may arrive after the desktop's of today.
    So an older scan arriving late is given a place before the later ones, which
    move up by one, and their observations with them.
    """
    values = [scan.get(k) for k in _SCAN] + [_now()]
    later = conn.execute(
        "SELECT MIN(id) FROM scan WHERE started_at > ?", (scan["started_at"],)).fetchone()[0]
    columns = ", ".join(_SCAN) + ", synced_at"
    marks = ", ".join("?" * len(values))
    if later is None:
        return int(conn.execute(f"INSERT INTO scan ({columns}) VALUES ({marks})", values).lastrowid)  # noqa: S608
    # Rows and the rows that point at them move one after the other, so the check
    # that they agree waits for the end of the transaction -- which must be open
    # for the pragma to mean anything.
    if not conn.in_transaction:
        conn.execute("BEGIN")
    conn.execute("PRAGMA defer_foreign_keys = ON")
    moving = conn.execute(
        "SELECT id FROM scan WHERE id >= ? ORDER BY id DESC", (later,)).fetchall()
    for (old,) in moving:
        conn.execute("UPDATE scan SET id = ? WHERE id = ?", (old + 1, old))
        conn.execute("UPDATE observation SET scan_id = ? WHERE scan_id = ?", (old + 1, old))
    conn.execute(f"INSERT INTO scan (id, {columns}) VALUES (?, {marks})", [later, *values])  # noqa: S608
    return int(later)


def receive(store: Store, data: bytes) -> dict:
    """Take one upload into this home. Adds; never replaces, never deletes."""
    if len(data) > MAX_BUNDLE_BYTES:
        raise SyncError("上传的内容太大。")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
        info = archive.getinfo("bundle.json")
        if info.file_size > MAX_JSON_BYTES:
            raise SyncError("上传的内容太大。")
        said = json.loads(archive.read(info))
    except (zipfile.BadZipFile, KeyError, ValueError) as exc:
        raise SyncError("上传的内容读不出来。") from exc
    if not isinstance(said, dict):
        raise SyncError("上传的内容读不出来。")
    _same_protocol(said)
    if int(said.get("epoch") or 0) != store.sync_epoch():
        raise SyncError("扫描数据在主机上被清空过；先同步（pull）再上传。")

    took = {"scans": 0, "known": 0, "observations": 0, "gallery": 0, "faces": 0,
            "weapon_kinds": 0, "aliases": 0, "wallet": 0, "icons": 0}
    scans = sorted((s for s in said.get("scans") or [] if _valid_scan(s)),
                   key=lambda s: s["started_at"])
    try:
        _take(store, said, scans, took)
    except (sqlite3.Error, TypeError, ValueError) as exc:
        raise SyncError("上传的内容不对，什么都没有写入。") from exc
    known = store.aliases()
    for wrong, right in (said.get("aliases") or {}).items():
        if isinstance(wrong, str) and isinstance(right, str) and wrong not in known:
            store.add_alias(wrong, right)
            took["aliases"] += 1
    for entry in archive.infolist():
        digest = entry.filename.removeprefix("icons/").removesuffix(".webp")
        if entry.filename != f"icons/{digest}.webp" or not _DIGEST.match(digest):
            continue                # only ever a name this code made up itself: never a path
        dest = store.icon_dir / f"{digest}.webp"
        if dest.exists() or entry.file_size > MAX_ICON_BYTES:
            continue
        blob = archive.read(entry)
        if blob[:4] == b"RIFF" and blob[8:12] == b"WEBP":
            dest.write_bytes(blob)
            took["icons"] += 1
    return took


def _take(store: Store, said: dict, scans: list[dict], took: dict) -> None:
    """The rows of one upload, all or none."""
    with store.conn:
        for scan in scans:
            if store.conn.execute("SELECT 1 FROM scan WHERE uid = ?", (scan["uid"],)).fetchone():
                took["known"] += 1
                continue
            scan_id = _insert_scan(store.conn, scan)
            rows = [[scan_id, *row] for row in scan["observations"]]
            store.conn.executemany(
                f"INSERT INTO observation (scan_id, {', '.join(_OBS)}) "  # noqa: S608
                f"VALUES ({', '.join('?' * (len(_OBS) + 1))})", rows)
            took["scans"] += 1
            took["observations"] += len(rows)
        for row in said.get("gallery") or []:
            if not isinstance(row, dict) or not _DIGEST.match(str(row.get("icon_hash"))) \
                    or row.get("tab") == _REFERENCE or not isinstance(row.get("rarity"), int):
                continue
            took["gallery"] += store.conn.execute(
                f"INSERT OR IGNORE INTO gallery ({', '.join(_GALLERY)}) "  # noqa: S608
                f"VALUES ({', '.join('?' * len(_GALLERY))})",
                [(_blob(row.get(k)) if k in ("embedding", "colour") else row.get(k))
                 for k in _GALLERY]).rowcount
        for row in said.get("faces") or []:
            if not isinstance(row, dict) or not _DIGEST.match(str(row.get("key"))):
                continue
            took["faces"] += store.conn.execute(
                f"INSERT OR IGNORE INTO holder_face ({', '.join(_FACE)}) "  # noqa: S608
                f"VALUES ({', '.join('?' * len(_FACE))})",
                [(_blob(row.get(k)) if k == "embedding" else row.get(k)) for k in _FACE]).rowcount
        for name, kind in (said.get("weapon_kinds") or {}).items():
            if isinstance(name, str) and isinstance(kind, str):
                took["weapon_kinds"] += store.conn.execute(
                    "INSERT OR IGNORE INTO weapon_kind(name, kind, seen_at) VALUES (?,?,?)",
                    (name, kind, _now())).rowcount
        # the wallet is "the last reading", by id: only a reading newer than the last one here
        last = store.conn.execute("SELECT MAX(read_at) FROM wallet").fetchone()[0] or ""
        for row in said.get("wallet") or []:
            read_at = row.get("read_at") if isinstance(row, dict) else None
            if isinstance(read_at, str) and read_at > last:
                store.conn.execute(
                    "INSERT INTO wallet (read_at, shells, astrite, confidence) VALUES (?,?,?,?)",
                    (row["read_at"], row.get("shells"), row.get("astrite"),
                     float(row.get("confidence") or 0)))
                last, took["wallet"] = row["read_at"], took["wallet"] + 1


def _valid_scan(scan: object) -> bool:
    if not isinstance(scan, dict) or not _UID.match(str(scan.get("uid"))):
        return False
    if not isinstance(scan.get("started_at"), str) or not isinstance(scan.get("source"), str):
        return False
    rows = scan.get("observations")
    return isinstance(rows, list) and all(
        isinstance(r, list) and len(r) == len(_OBS) and isinstance(r[0], str)
        and isinstance(r[3], str) and _DIGEST.match(r[3]) for r in rows)


def state_for(store: Store, theirs: dict) -> dict:
    """What a scanner should know that it does not: the difference from what it has."""
    _same_protocol(theirs)
    epoch = store.sync_epoch()
    fresh = int(theirs.get("epoch") or 0) != epoch       # it must start over: send everything
    their_gallery = {} if fresh else (theirs.get("gallery") or {})
    their_faces = {} if fresh else (theirs.get("faces") or {})
    gallery, names = [], {}
    for row in store.conn.execute(
        f"SELECT {', '.join(_GALLERY)} FROM gallery WHERE tab IS NULL OR tab != ?",  # noqa: S608
        (_REFERENCE,)
    ):
        if row["icon_hash"] not in their_gallery:
            gallery.append({k: (_b64(row[k]) if k in ("embedding", "colour") else row[k])
                            for k in _GALLERY})
        elif their_gallery[row["icon_hash"]] != row["item_name"]:
            names[row["icon_hash"]] = row["item_name"]
    faces, face_names = [], {}
    for row in store.conn.execute(f"SELECT {', '.join(_FACE)} FROM holder_face"):  # noqa: S608
        if row["key"] not in their_faces:
            faces.append({k: (_b64(row[k]) if k == "embedding" else row[k]) for k in _FACE})
        elif their_faces[row["key"]] != row["name"]:
            face_names[row["key"]] = row["name"]
    pulls = store.conn.execute(
        "SELECT imported_at, data FROM pull_import ORDER BY id DESC LIMIT 1").fetchone()
    mine_gallery, mine_faces = _learned(store)
    return {
        "protocol": PROTOCOL, "epoch": epoch,
        "gallery": gallery, "names": names, "faces": faces, "face_names": face_names,
        # what the scanner has that this home does not: removed here, or new there --
        # the scanner knows which (sync_seen)
        "gone": {"gallery": sorted(set(their_gallery) - set(mine_gallery)),
                 "face": sorted(set(their_faces) - set(mine_faces))},
        "aliases": store.aliases(), "weapon_kinds": store.weapon_kinds(),
        "pulls": {"imported_at": pulls["imported_at"], "data": json.loads(pulls["data"])}
        if pulls else None,
    }


# ------------------------------------------------------------------ the catalogue


def catalogue_manifest(directory: Path) -> dict[str, list]:
    """Every file of the catalogue: its path -> [size, sha1]. The scanner asks for
    what differs. Hand edits are a file among the others (overrides.json)."""
    out: dict[str, list] = {}
    if not directory.is_dir():
        return out
    for path in sorted(directory.rglob("*")):
        if path.is_file() and not any(part.startswith(".") for part in path.parts):
            rel = path.relative_to(directory).as_posix()
            stat = path.stat()
            # a file that has not changed is not read again: a home is asked before every scan
            seen = (str(path), stat.st_size, stat.st_mtime_ns)
            if seen not in _HASHED:
                _HASHED[seen] = _sha1(path)
            out[rel] = [stat.st_size, _HASHED[seen]]
    return out


_HASHED: dict[tuple[str, int, int], str] = {}


def _sha1(path: Path) -> str:
    digest = hashlib.sha1(usedforsecurity=False)
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _plain_path(rel: str) -> bool:
    """A relative path that goes down and nowhere else."""
    return (bool(rel) and "\\" not in rel and not rel.startswith("/")
            and all(part not in ("", ".", "..") for part in rel.split("/")))


def catalogue_file(directory: Path, rel: str) -> Path | None:
    """The file a manifest named, or None for anything that is not inside the catalogue."""
    if not _plain_path(rel):
        return None
    path = (directory / rel).resolve()
    return path if path.is_file() and directory.resolve() in path.parents else None


# ------------------------------------------------------------------- keys and config


def home_key(data_dir: Path, create: bool = False) -> str | None:
    """The key a scanner must show to upload. Kept beside the data, made on first use."""
    path = data_dir / HOME_KEY_FILE
    if path.is_file():
        return path.read_text(encoding="utf-8").strip() or None
    if not create:
        return None
    data_dir.mkdir(parents=True, exist_ok=True)
    key = secrets.token_urlsafe(32)
    path.write_text(key + "\n", encoding="utf-8")
    return key


def key_matches(expected: str | None, shown: str | None) -> bool:
    return bool(expected) and bool(shown) and hmac.compare_digest(expected.encode(), shown.encode())


#: The port a home listens on when an address does not say (deploy/home, docs/nas.md).
HOME_PORT = 4000
TAILNET = ipaddress.ip_network("100.64.0.0/10")


def _resolve(host: str) -> str | None:
    """The address a name stands for, by this machine's resolver -- MagicDNS for a tailnet
    device's own name; None when it stands for nothing."""
    try:
        return socket.getaddrinfo(host, None, family=socket.AF_INET)[0][4][0]
    except (OSError, IndexError):
        return None


def check_address(url: str, resolve: Callable[[str], str | None] = _resolve) -> str:
    """A home's address, tidied -- or SyncError if it is not on the tailnet.

    A scanner sends its scans where the user said and nowhere else, and where the
    user may say is the tailnet (hard constraint 3): a `…ts.net` name, a Tailscale
    address (100.64.0.0/10), or this machine itself. Not the LAN, not the internet.

    Written the ways Tailscale shows it (D189): the MagicDNS name without http:// and
    the port, the 100.x address the admin console copies, or just the device's name
    (`wuwa-home`) -- taken only when it resolves into 100.64.0.0/10. With no scheme
    given, http:// and port 4000 are put in.
    """
    said = url.strip()
    bare = bool(said) and "://" not in said
    parts = urllib.parse.urlsplit(f"http://{said}" if bare else said)
    host = (parts.hostname or "").lower()
    if parts.scheme not in ("http", "https") or not host or parts.username or parts.query:
        raise SyncError("主机地址要写成 http://名字.ts.net:端口、100.x，"
                        "或者设备名（如 wuwa-home）。")
    ok = host == "localhost" or host.endswith(".ts.net")
    if not ok:
        try:
            ip = ipaddress.ip_address(host)
            ok = ip.is_loopback or ip in TAILNET
        except ValueError:
            # a device's own name, which MagicDNS answers: only if it is a tailnet address
            found = resolve(host) if "." not in host else None
            try:
                ok = found is not None and ipaddress.ip_address(found) in TAILNET
            except ValueError:
                ok = False
    if not ok:
        raise SyncError("主机只能是 tailnet 上的地址（…ts.net、100.x 或 Tailscale 里的设备名），"
                        "不能是局域网或公网地址。")
    port = parts.port or (HOME_PORT if bare else None)
    return f"{parts.scheme}://{host}" + (f":{port}" if port else "")


def read_home(data_dir: Path) -> dict | None:
    """Where this scanner sends its scans: {"url", "key"}, or None for a machine on its own."""
    path = data_dir / HOME_FILE
    try:
        said = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return said if isinstance(said, dict) and said.get("url") and said.get("key") else None


def write_home(data_dir: Path, url: str | None, key: str | None = None) -> None:
    path = data_dir / HOME_FILE
    if not url:
        path.unlink(missing_ok=True)
        return
    data_dir.mkdir(parents=True, exist_ok=True)
    said = {"url": check_address(url), "key": key}
    path.write_text(json.dumps(said, indent=1) + "\n", encoding="utf-8")


def downloads_folder() -> Path:
    """Where this user's browser saves a download (D220): Windows' own Downloads folder, wherever
    it was moved to; ~/Downloads elsewhere, and when Windows will not say."""
    if sys.platform == "win32":
        try:
            import ctypes
            import uuid
            from ctypes import wintypes

            downloads = uuid.UUID("{374DE290-123F-4565-9164-39C4925E467B}")    # FOLDERID_Downloads

            class _Guid(ctypes.Structure):
                _fields_ = [("data", ctypes.c_ubyte * 16)]

            path = ctypes.c_wchar_p()
            got = ctypes.windll.shell32.SHGetKnownFolderPath(
                ctypes.byref(_Guid((ctypes.c_ubyte * 16).from_buffer_copy(downloads.bytes_le))),
                0, None, ctypes.byref(path))
            if got == 0 and path.value:
                folder = Path(path.value)
                ctypes.windll.ole32.CoTaskMemFree(ctypes.cast(path, wintypes.LPVOID))
                return folder
        except (OSError, AttributeError, ValueError):
            pass
    return Path.home() / "Downloads"


def find_key(said: str | None) -> tuple[str | None, Path | None]:
    """The home's key from what was typed at the key question (D220): the key itself; a path to
    a key file (one dragged into the window); or nothing, which takes the newest home*.key in
    Downloads -- a browser names a second download `home (1).key`. Returns (key, the file it
    came from), or (None, None) when there is none."""
    said = (said or "").strip().strip('"').strip("'")
    if said:
        given = Path(said)
        try:
            if given.is_file():
                return given.read_text(encoding="utf-8").strip() or None, given
        except (OSError, ValueError):
            pass
        return said, None
    folder = downloads_folder()
    found = sorted((p for p in folder.glob("home*.key") if p.is_file()),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    for path in found:
        try:
            key = path.read_text(encoding="utf-8").strip()
        except (OSError, ValueError):
            continue
        if key:
            return key, path
    return None, None


# ------------------------------------------------------------- how far it has got


#: The speed told is that of the last few seconds: long enough not to jump with
#: every block, short enough to be the speed now.
RATE_WINDOW = 3.0
#: While bytes move, whoever watches is told at most this often (seconds). A
#: step's start, each thing finished and the end are always told.
TELL_EVERY = 0.1
#: What crosses is sent and read in blocks of this size, so it can be counted.
_BLOCK = 64 * 1024


class Transfer:
    """One half of a sync as it goes (D156): what is moving, how much is left, how fast.

    Headless, like the rest of this module: `tell` is handed a plain dict when
    something changed and None when the half is over. The terminal, the live
    page and the phone's page each word it themselves.

    It fills by bytes where the total is known -- an upload is one zip of a known
    size, the catalogue's files have their sizes in the home's manifest -- and by
    count where it is not: crops arrive one by one, each as big as it turns out.
    The speed is the transfer's own, the bytes that crossed over the time they
    took. Nothing is sent to measure it.
    """

    def __init__(self, way: str, tell: Callable[[dict | None], None],
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.way, self._tell, self._clock = way, tell, clock    # way: "up" | "down"
        self.step = ""
        self.items = self.items_done = self.crossed = 0
        self.size: int | None = None
        self.holds: dict[str, int] = {}
        self._item_from = 0
        self._told = float("-inf")
        self._marks: deque[tuple[float, int]] = deque()
        self._all = 0

    def begin(self, step: str, items: int = 0, size: int | None = None, **holds: int) -> None:
        """A new step: `items` things to move, `size` bytes in all where that is known."""
        self.step, self.items, self.size, self.holds = step, items, size, holds
        self.items_done = self.crossed = self._item_from = 0
        self._say()

    def expect(self, size: int | None) -> None:
        """The one thing this step moves turns out to be `size` bytes (its reply said so)."""
        if size and self.size is None and self.items == 1:
            self.size = size

    def moved(self, count: int) -> None:
        """`count` more bytes crossed."""
        if not self.step or count <= 0:
            return                  # between steps: a question to the home, not the cargo
        self.crossed += count
        self._all += count
        now = self._clock()
        self._marks.append((now, self._all))
        while len(self._marks) > 2 and now - self._marks[1][0] >= RATE_WINDOW:
            self._marks.popleft()
        if now - self._told >= TELL_EVERY:
            self._say()

    def whole(self, size: int) -> None:
        """The thing being moved was `size` bytes in all. A transport that counts
        as it goes has said so already; one that does not says it here, once."""
        self.moved(self._item_from + size - self.crossed)

    def done(self) -> None:
        """One thing finished."""
        self.items_done += 1
        self._item_from = self.crossed
        self._say()

    def end(self) -> None:
        self._tell(None)

    def rate(self) -> float | None:
        """Bytes a second over the last few seconds, or None before it can be said."""
        if len(self._marks) < 2:
            return None
        (t0, b0), (t1, b1) = self._marks[0], self._marks[-1]
        return (b1 - b0) / (t1 - t0) if t1 - t0 >= 0.05 else None

    def said(self) -> dict:
        if self.size:
            fraction = min(self.crossed / self.size, 1.0)
        elif self.items:
            fraction = min(self.items_done / self.items, 1.0)
        else:
            fraction = None         # not known yet: the bar shows only that something moves
        return {"way": self.way, "step": self.step, "items": self.items,
                "items_done": self.items_done, "bytes": self.size, "bytes_done": self.crossed,
                "rate": self.rate(), "fraction": fraction, "holds": dict(self.holds)}

    def _say(self) -> None:
        self._told = self._clock()
        self._tell(self.said())


def _blocks(body: bytes, moved: Callable[[int], None]) -> Iterator[bytes]:
    """`body` a block at a time, saying so as each one has gone."""
    for start in range(0, len(body), _BLOCK):
        block = body[start:start + _BLOCK]
        yield block
        moved(len(block))


# ------------------------------------------------------------------------ the client


class EarlyPush:
    """A tab finished during a scan, sent home while the scan goes on (D173).

    `send` is called from the scan and returns at once; one worker sends, in order, every
    finished scan the home lacks -- `Home.push`, so one that failed before goes along with
    the next. A home out of reach costs the scan nothing: it is said, and what was not sent
    waits here and goes at the end (or with the next scan). `wait` lets the worker finish.
    """

    def __init__(self, home: Callable[[], Home], db: Path | str,
                 say: Callable[[str], None] = print) -> None:
        import queue
        import threading

        self._home, self._db, self._say = home, Path(db), say
        self._jobs: queue.Queue[str | None] = queue.Queue()
        self._worker = threading.Thread(target=self._run, name="early-push", daemon=True)
        self._started = False

    def send(self, tab: object) -> None:
        """`tab` (a closed `TabScan`) is finished: send it, and anything waiting, home."""
        if not self._started:
            self._started = True
            self._worker.start()
        self._jobs.put(getattr(tab, "label", None) or "?")

    def _run(self) -> None:
        while (label := self._jobs.get()) is not None:
            store = Store(self._db)
            try:
                sent = self._home().push(store)
                if sent.get("scans"):
                    self._say(f"home: sent {label} while scanning")
            except SyncError as exc:
                self._say(f"! home: {exc} -- {label} waits here and goes at the end")
            except Exception as exc:  # noqa: BLE001 -- a sender's slip must never stop a scan
                self._say(f"! home: {label} not sent ({exc}) -- it goes at the end")
            finally:
                store.close()

    def wait(self) -> None:
        """Let what was handed over finish being sent."""
        if self._started:
            self._jobs.put(None)
            self._worker.join()


class Home:
    """The home, as a scanner speaks to it."""

    def __init__(self, url: str, key: str | None = None, timeout: float = 30.0) -> None:
        self.url, self.key, self.timeout = check_address(url), key, timeout
        #: Who is told how a push or a pull is going (D156). Nobody, by default.
        self.tell: Callable[[dict | None], None] | None = None
        self._going: Transfer | None = None

    @contextlib.contextmanager
    def _half(self, way: str) -> Iterator[Transfer]:
        """One half of a sync, watched from its first step to its end."""
        if self._going is not None:     # inside one already: the catalogue, within a pull
            yield self._going
            return
        going = self._going = Transfer(way, self.tell or (lambda said: None))
        try:
            yield going
        finally:
            self._going = None
            going.end()

    def _call(self, path: str, body: bytes | None = None, kind: str = "application/json") -> bytes:
        going = self._going
        headers = {"X-Wuwa-Key": self.key} if self.key else {}
        data: bytes | Iterator[bytes] | None = body
        if body is not None:
            headers["Content-Type"] = kind
            if going is not None and going.way == "up":
                # in blocks, its length said first: counted as it goes, and each
                # block has the timeout to itself where the whole upload shared one
                headers["Content-Length"] = str(len(body))
                data = _blocks(body, going.moved)
        request = urllib.request.Request(self.url + path, data=data, headers=headers)  # noqa: S310
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as reply:  # noqa: S310
                if going is None or going.way != "down":
                    return reply.read()
                length = reply.headers.get("Content-Length") or ""
                going.expect(int(length) if length.isdigit() else None)
                parts = []
                while block := reply.read(_BLOCK):
                    parts.append(block)
                    going.moved(len(block))
                return b"".join(parts)
        except urllib.error.HTTPError as exc:
            try:
                detail = json.loads(exc.read()).get("detail")
            except (ValueError, AttributeError):
                detail = None
            raise SyncError(str(detail or f"主机回答 {exc.code}")) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise SyncError(f"连不上主机 {self.url}（{getattr(exc, 'reason', exc)}）") from exc

    def _ask(self, path: str, body: bytes | None = None, kind: str = "application/json") -> bytes:
        """`_call`, with whoever is watching told what crossed."""
        reply = self._call(path, body, kind)
        if self._going is not None:
            self._going.whole(len(body or b"") if self._going.way == "up" else len(reply))
        return reply

    def _json(self, path: str, said: dict | None = None) -> dict:
        body = json.dumps(said, ensure_ascii=False).encode() if said is not None else None
        try:
            return json.loads(self._ask(path, body))
        except ValueError as exc:
            raise SyncError("主机的回答读不出来；那个地址上是这个程序吗？") from exc

    def hello(self) -> dict:
        said = self._json("/api/sync/hello")
        if said.get("app") != "wuwa-vision" or not said.get("home"):
            raise SyncError("那个地址上的程序不是主机（要用 serve --home 启动）。")
        _same_protocol(said)
        return said

    def check(self) -> dict:
        """Is this a home, and is this its key? What it said of itself, if so."""
        said = self.hello()
        self._json("/api/sync/need", {"protocol": PROTOCOL, "epoch": said["epoch"]})
        return said

    def push(self, store: Store) -> dict:
        """Hand over every finished scan the home lacks. Nothing to send is not an error.

        In parts, one scan (one tab) each, oldest first (D171): the home takes in a piece at a
        time instead of a whole session at once, and a connection lost on the way costs only
        the part it was carrying -- the parts before it are home, and marked so."""
        scans = unsent_scans(store)
        if not scans:
            return {"scans": 0, "known": 0}
        total: dict[str, int] = {}
        for i, scan in enumerate(scans):
            took = self._push_part(store, offer(store, [scan], everything=i == len(scans) - 1))
            for key, value in took.items():
                total[key] = total.get(key, 0) + int(value or 0)
        return total

    def _push_part(self, store: Store, offered: dict) -> dict:
        """One part of a push: what the home lacks of `offered`, sent and marked sent."""
        wanted = self._json("/api/sync/need", offered)
        took = {"scans": 0}
        if any(wanted.get(k) for k in ("scans", "gallery", "faces", "icons")):
            packed = bundle(store, wanted)
            with self._half("up") as going:
                going.begin("scans", size=len(packed), scans=len(wanted.get("scans") or []),
                            crops=len(wanted.get("icons") or []))
                sent = self._ask("/api/sync/scans", packed, "application/zip")
                going.done()
            took = json.loads(sent)
        mark_sent(store, offered["scans"])
        mark_seen(store, offered["gallery"], offered["faces"])     # it had them, or has them now
        return {**took, "known": len(wanted.get("known") or [])}

    def pull(self, store: Store, catalogue_dir: Path | None = None) -> dict:
        """Bring this scanner's copy up to what the home knows."""
        with self._half("down") as going:
            return self._pull(store, catalogue_dir, going)

    def _pull(self, store: Store, catalogue_dir: Path | None, going: Transfer) -> dict:
        going.begin("learned", items=1)
        state = self._json("/api/sync/state", have(store))
        _same_protocol(state)
        took: dict = {}
        if int(state.get("epoch") or 0) != store.sync_epoch():
            took["set_aside"] = start_over(store, int(state["epoch"])).as_posix()
            going.begin("learned", items=1)
            state = self._json("/api/sync/state", have(store))
        going.done()
        asked = have(store)
        took.update(apply_state(store, state))
        gone = state.get("gone") or {}
        mark_seen(store,
                  (set(asked["gallery"]) - set(gone.get("gallery") or []))
                  | {r.get("icon_hash") for r in state.get("gallery") or []},
                  (set(asked["faces"]) - set(gone.get("face") or []))
                  | {r.get("key") for r in state.get("faces") or []})
        crops: list[str] = []
        for row in [*(state.get("gallery") or []), *(state.get("faces") or [])]:
            digest = row.get("icon_hash") or row.get("key")
            if (_DIGEST.match(str(digest)) and digest not in crops
                    and not (store.icon_dir / f"{digest}.webp").exists()):
                crops.append(digest)
        fetched = 0
        if crops:
            going.begin("crops", items=len(crops))
        for digest in crops:
            try:
                (store.icon_dir / f"{digest}.webp").write_bytes(
                    self._ask(f"/api/icon/{digest}.webp"))
                fetched += 1
            except SyncError:
                pass                # a row whose crop the home no longer has: the row is enough
            going.done()
        took["icons"] = fetched
        if catalogue_dir is not None:
            took["catalogue"] = self.pull_catalogue(catalogue_dir)
        return took

    def pull_catalogue(self, directory: Path) -> int:
        """Fetch the catalogue files that differ from the home's. Adds and replaces;
        a file only this machine has is left alone."""
        theirs = self._json("/api/sync/catalogue").get("files") or {}
        mine = catalogue_manifest(directory)
        differ = [(rel, size) for rel, (size, digest) in theirs.items()
                  if mine.get(rel) != [size, digest] and _plain_path(rel)]
        if not differ:
            return 0
        with self._half("down") as going:
            # the manifest gives every file's size, so this step can fill by bytes
            going.begin("catalogue", items=len(differ),
                        size=sum(size for _, size in differ if isinstance(size, int)) or None)
            for rel, _ in differ:
                blob = self._ask("/api/sync/catalogue/" + urllib.parse.quote(rel))
                dest = directory / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                part = dest.with_name(dest.name + ".part")
                part.write_bytes(blob)
                part.replace(dest)
                going.done()
        return len(differ)
