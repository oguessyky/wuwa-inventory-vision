# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""SQLite persistence. Append-only scan snapshots (PLAN.md D12).

Scans are never overwritten, so "what changed since last scan" is a SQL query
rather than a feature to build later. Icon crops live on disk addressed by
content hash, keeping the database small and de-duplicating automatically.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from PIL import Image

SCHEMA_VERSION = 13
#: Material targets share the craft_target table with the dish ones, under this
#: prefix: one "what the user wants kept" table, two kinds of thing in it (D84).
MATERIAL_TARGET_PREFIX = "材料:"
#: A base amount (D158) rides on the same table under a prefix of its own: the
#: least to keep of something a shop sells, beside its target and not instead of it.
BASE_AMOUNT_PREFIX = "底数:"
#: The echoes' base among the base amounts: one number for all four 密音筒, how many
#: five-star echoes to +25 there should be EXP for (D161). Not a thing's name.
ECHO_BASE = "五星声骸+25"
#: app_setting key: how many times the scans were wiped. A scanner compares it
#: with the home's to know its own copy is of a past that was thrown away (D145).
SYNC_EPOCH = "sync.epoch"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scan (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at   TEXT    NOT NULL,
    source       TEXT    NOT NULL,
    tab_label    TEXT,
    header_total INTEGER,
    frame_count  INTEGER NOT NULL DEFAULT 0,
    tile_count   INTEGER NOT NULL DEFAULT 0,
    complete     INTEGER NOT NULL DEFAULT 0,
    -- v13 (D145). `uid` is the scan's own name, the same on every machine that
    -- holds it: ids are per database, and a scan sent to the home gets a new one
    -- there. `synced_at`: on a scanner, when the home took it; on the home, when
    -- it arrived. NULL on a scan that has never crossed.
    uid          TEXT,
    synced_at    TEXT,
    -- D197: which version of the app made this scan; NULL from scanners before 1.1.1
    app_version  TEXT
);

CREATE TABLE IF NOT EXISTS observation (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id     INTEGER NOT NULL REFERENCES scan(id) ON DELETE CASCADE,
    frame       TEXT    NOT NULL,
    row         INTEGER NOT NULL,
    col         INTEGER NOT NULL,
    icon_hash   TEXT    NOT NULL,
    rarity      INTEGER NOT NULL,
    rarity_conf REAL    NOT NULL,
    count       INTEGER,
    count_conf  REAL    NOT NULL DEFAULT 0.0,
    item_name   TEXT,
    needs_review INTEGER NOT NULL DEFAULT 0,
    -- Which stitched item this sighting belongs to (v3). Not icon_hash: live
    -- capture never reproduces a crop bit-for-bit, so one item yields many hashes.
    item_key    TEXT,
    -- Names this tile looked identical to (v5): the main app's 待确认 filter (D45).
    rivals      TEXT,
    -- 武器 tiles only (v11, D61): the weapon's level, and the portrait of whoever
    -- has it equipped (holder_face.key). NULL on every bag tile. Weapons never
    -- stack, so on those tiles `count` is that copy's 谐振阶数, not a quantity
    -- (D63): 飞逝 sat on seven tiles, six showing 1 and one showing 5.
    level       INTEGER,
    holder_key  TEXT
);

CREATE INDEX IF NOT EXISTS ix_obs_scan ON observation(scan_id);
CREATE INDEX IF NOT EXISTS ix_obs_hash ON observation(icon_hash);

-- Counts corrected by hand on the main app (D45). A manual count is the newest
-- reading of its item until a later scan reads that item again. `ident` is the
-- item's name, or "key:<item_key>" for an item nobody has named yet.
CREATE TABLE IF NOT EXISTS manual_count (
    ident  TEXT PRIMARY KEY,
    count  INTEGER NOT NULL,
    set_at TEXT NOT NULL
);

-- The cooking page's stock targets (D45 decision 8): a per-item override of
-- the per-type default kept in app_setting ("target:菜肴", "target:药品").
CREATE TABLE IF NOT EXISTS craft_target (
    name   TEXT PRIMARY KEY,
    target INTEGER NOT NULL
);

-- 食谱/配方 the user ticked as learned (D45 decision 7). The bag scan cannot see
-- them: learned recipes live in the game's cooking menu, not the inventory.
CREATE TABLE IF NOT EXISTS learned_recipe (
    name TEXT PRIMARY KEY
);

-- The planner's entries (D47): one resonator or weapon, from its current state to
-- the target the user set. `state` is JSON: {"current": {...}, "target": {...}}.
CREATE TABLE IF NOT EXISTS plan (
    id         INTEGER PRIMARY KEY,
    kind       TEXT NOT NULL CHECK (kind IN ('resonator', 'weapon')),
    name       TEXT NOT NULL,
    state      TEXT NOT NULL,
    position   INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

-- The bag's currency counters, read off the top bar during a scan (D48).
CREATE TABLE IF NOT EXISTS wallet (
    id         INTEGER PRIMARY KEY,
    read_at    TEXT NOT NULL,
    shells     INTEGER,
    astrite    INTEGER,
    confidence REAL NOT NULL
);

-- Where each resonator stands, as the user entered it (D50): owned or not, and
-- the planner's state JSON (ascension, skill levels, nodes). The planner's
-- "current" for a resonator is this row.
CREATE TABLE IF NOT EXISTS resonator_state (
    name       TEXT PRIMARY KEY,
    owned      INTEGER NOT NULL DEFAULT 1,
    state      TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- The latest imported pull export, reduced to counts (D53): copies per resonator
-- and weapon, never the player id or the pull list. A new upload replaces it.
CREATE TABLE IF NOT EXISTS pull_import (
    id          INTEGER PRIMARY KEY,
    imported_at TEXT NOT NULL,
    data        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_setting (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- 更新 › 识别 (D167): a learned picture the catalogue doubts, which a person said is rightly
-- named. `name` is the name it was confirmed under: renamed since, it is open to doubt again.
CREATE TABLE IF NOT EXISTS crop_confirmed (
    icon_hash TEXT PRIMARY KEY,
    name      TEXT NOT NULL,
    at        TEXT NOT NULL
);

-- 猜谜 (D147): one row per round. `day` is the game's day for the daily round
-- (one a day) and NULL for a free one; `guesses` is the names guessed, in order;
-- `notes` is what the player wrote on cells of a 噩梦 round ("row:column" -> mark);
-- `result` is NULL while the round goes on.
CREATE TABLE IF NOT EXISTS guess_round (
    id         INTEGER PRIMARY KEY,
    mode       TEXT NOT NULL CHECK (mode IN ('daily', 'free')),
    day        TEXT,
    level      TEXT NOT NULL,
    answer     TEXT NOT NULL,
    guesses    TEXT NOT NULL DEFAULT '[]',
    notes      TEXT NOT NULL DEFAULT '{}',
    result     TEXT CHECK (result IN ('won', 'lost')),
    started_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS guess_round_day ON guess_round (day) WHERE mode = 'daily';

-- Name corrections made by the user (D40). OCR misreads a name the same way every
-- time (改造镣环 -> 改造环 at 1.00), so one fix rewrites every later read of it.
CREATE TABLE IF NOT EXISTS name_alias (
    wrong      TEXT PRIMARY KEY,
    right      TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- What kind of weapon a name is, in the game's own words: the category line of
-- its detail panel ("音感仪"), learned when the weapon is clicked (D98). The wiki
-- is the first source; this covers the weapons its build pages do not list.
CREATE TABLE IF NOT EXISTS weapon_kind (
    name    TEXT PRIMARY KEY,
    kind    TEXT NOT NULL,
    seen_at TEXT NOT NULL
);

-- Gallery: the crown jewels (D17). Built by hover bootstrap in Milestone 3.
-- The portraits worn by 武器 tiles (v11, D61). Self-building like `gallery`:
-- a face is stored the first time it is seen and named later, by hand, on the
-- 武器 page -- the reference avatars are close enough to spot a portrait but not
-- to name one.
CREATE TABLE IF NOT EXISTS holder_face (
    key        TEXT PRIMARY KEY,
    name       TEXT,
    backbone   TEXT,
    embedding  BLOB,
    created_at TEXT NOT NULL,
    named_at   TEXT,
    -- Who the reference avatars say it might be, most alike first. A shortlist
    -- for the user's picker, never an answer (D61).
    suggestions TEXT
);

-- On a scanner (D145): the learned rows its home is known to hold -- it took them
-- in an upload, or sent them here. A row listed here that the home no longer has
-- was removed there, and is removed here; one not listed is new, and is offered.
CREATE TABLE IF NOT EXISTS sync_seen (
    kind TEXT NOT NULL,
    key  TEXT NOT NULL,
    PRIMARY KEY (kind, key)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS gallery (
    icon_hash  TEXT PRIMARY KEY,
    -- Nullable: the gallery self-builds from scans, and real names only arrive
    -- later from the detail-panel hover bootstrap (PLAN.md D3/D17).
    item_name  TEXT,
    rarity     INTEGER NOT NULL,
    tab        TEXT,
    backbone   TEXT,
    embedding  BLOB,
    created_at TEXT NOT NULL,
    -- v4: colour thumbnail (recognize.appearance) of crops taken from the game
    -- screen. NULL for reference icons, whose colours do not match the screen.
    colour     BLOB
);
"""


@dataclass(frozen=True, slots=True)
class Observation:
    frame: str
    row: int
    col: int
    icon_hash: str
    rarity: int
    rarity_conf: float
    count: int | None
    count_conf: float
    item_name: str | None = None
    needs_review: bool = False
    box: tuple[int, int, int, int] | None = field(default=None, compare=False)
    """(x0, y0, x1, y1) in the frame. Lets the stitcher place a tile in the grid."""
    descriptor: np.ndarray | None = field(default=None, compare=False, repr=False)
    """Small appearance vector (stitch.describe). Never persisted."""
    item_key: str | None = None
    from_panel: bool = False
    rivals: tuple[str, ...] = ()
    """Names this tile is indistinguishable from (identical art); needs a click."""
    level: int | None = None
    """武器 tiles: the weapon's level, read from its footer (D61)."""
    holder_key: str | None = None
    """武器 tiles: the portrait of whoever has it equipped (holder_face.key)."""
    """Name and count came from the detail panel (the game's own words), not a guess."""


def _old_scan_uid(row: sqlite3.Row) -> str:
    """The name of a scan that was made before scans had names (v13)."""
    said = "|".join(
        str(row[k]) for k in ("id", "started_at", "source", "tab_label", "header_total"))
    return hashlib.sha256(said.encode()).hexdigest()[:32]


def icon_hash(icon: np.ndarray) -> str:
    """Content hash of an icon crop.

    Resolution-normalised first (D17): the desktop renders ~201px tiles and the
    laptop will not, so hashing raw pixels would make one machine's gallery
    useless on the other.
    """
    norm = np.asarray(Image.fromarray(icon).convert("RGB").resize((64, 64), Image.LANCZOS))
    return hashlib.sha256(norm.tobytes()).hexdigest()[:32]


class Store:
    """Thin SQLite wrapper. No ORM: the schema is small and explicit."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(_SCHEMA)
        self._migrate()
        self.conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        self.conn.commit()

    def _migrate(self) -> None:
        """Apply forward migrations. Schema changes must never require a manual wipe."""
        row = self.conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
        current = int(row["value"]) if row else SCHEMA_VERSION

        if current < 2:
            # v1 declared gallery.item_name NOT NULL, which blocks the self-building
            # gallery (entries exist before their name is known). SQLite cannot drop
            # a NOT NULL constraint in place, so rebuild the table.
            self.conn.executescript(
                """
                ALTER TABLE gallery RENAME TO gallery_v1;
                CREATE TABLE gallery (
                    icon_hash  TEXT PRIMARY KEY,
                    item_name  TEXT,
                    rarity     INTEGER NOT NULL,
                    tab        TEXT,
                    backbone   TEXT,
                    embedding  BLOB,
                    created_at TEXT NOT NULL
                );
                INSERT INTO gallery SELECT * FROM gallery_v1;
                DROP TABLE gallery_v1;
                """
            )
            self.conn.commit()

        cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(observation)")}
        if "item_key" not in cols:
            self.conn.execute("ALTER TABLE observation ADD COLUMN item_key TEXT")
            self.conn.commit()
        if "rivals" not in cols:
            self.conn.execute("ALTER TABLE observation ADD COLUMN rivals TEXT")
            self.conn.commit()

        rcols = {r["name"] for r in self.conn.execute("PRAGMA table_info(resonator_state)")}
        if rcols and "chain" not in rcols:
            self.conn.execute("ALTER TABLE resonator_state ADD COLUMN chain INTEGER")
            self.conn.commit()

        fcols = {r["name"] for r in self.conn.execute("PRAGMA table_info(holder_face)")}
        if fcols and "suggestions" not in fcols:
            self.conn.execute("ALTER TABLE holder_face ADD COLUMN suggestions TEXT")
            self.conn.commit()

        if "level" not in cols:
            self.conn.execute("ALTER TABLE observation ADD COLUMN level INTEGER")
            self.conn.execute("ALTER TABLE observation ADD COLUMN holder_key TEXT")
            self.conn.commit()

        gcols = {r["name"] for r in self.conn.execute("PRAGMA table_info(gallery)")}
        if "colour" not in gcols:
            self.conn.execute("ALTER TABLE gallery ADD COLUMN colour BLOB")
            self.conn.commit()

        self._give_scans_names()
        self._version_scans()

    def _version_scans(self) -> None:
        """`scan.app_version` (D197). Several requests may open the database at once after
        an update (see `_give_scans_names`): the column is added under a write lock, once."""
        def has() -> bool:
            columns = self.conn.execute("PRAGMA table_info(scan)")
            return "app_version" in {r["name"] for r in columns}

        if has():
            return
        self.conn.commit()
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            if not has():
                self.conn.execute("ALTER TABLE scan ADD COLUMN app_version TEXT")
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise

    def _give_scans_names(self) -> None:
        """v13: `scan.uid` and `scan.synced_at`, a name for every scan made before, and
        the index that keeps names unique.

        The first page a browser loads after an update asks for several things at once,
        and each request opens the database: all of them arrive here together. So the
        step is taken by one, under a write lock the others wait for, and each looks
        again once it holds the lock -- two `ALTER TABLE`s for the same column is an
        error, and was a page that came up empty.
        """
        def done() -> bool:
            columns = {r["name"] for r in self.conn.execute("PRAGMA table_info(scan)")}
            indexed = self.conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = 'ux_scan_uid'"
            ).fetchone()
            return "uid" in columns and indexed is not None and not self.conn.execute(
                "SELECT 1 FROM scan WHERE uid IS NULL LIMIT 1").fetchone()

        if done():
            return
        self.conn.commit()
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            columns = {r["name"] for r in self.conn.execute("PRAGMA table_info(scan)")}
            if "uid" not in columns:
                self.conn.execute("ALTER TABLE scan ADD COLUMN uid TEXT")
                self.conn.execute("ALTER TABLE scan ADD COLUMN synced_at TEXT")
            # A scan made before v13 is named after what it is, not at random: the
            # database is copied to the home once, and both copies must then call each
            # old scan the same thing or the first upload would send them all again.
            for row in self.conn.execute(
                "SELECT id, started_at, source, tab_label, header_total FROM scan "
                "WHERE uid IS NULL"
            ).fetchall():
                self.conn.execute(
                    "UPDATE scan SET uid = ? WHERE id = ?", (_old_scan_uid(row), row["id"]))
            self.conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_scan_uid ON scan(uid)")
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise

    @property
    def icon_dir(self) -> Path:
        d = self.path.parent / "icons"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_icon(self, digest: str, icon: np.ndarray) -> Path:
        """Write an icon crop, addressed by content hash. Idempotent.

        Grid crops never contain the UID watermark (it sits bottom-right, outside
        the grid), so no redaction is needed here -- but whole-frame writes would
        need it, which is one reason frames are not archived by default (D12).
        """
        dest = self.icon_dir / f"{digest}.webp"
        if not dest.exists():
            Image.fromarray(icon).save(dest, "WEBP", quality=92)
        return dest

    def close(self) -> None:
        self.conn.close()

    def begin_scan(self, source: str, tab_label: str | None, header_total: int | None) -> int:
        from ..versions import this_version

        cur = self.conn.execute(
            "INSERT INTO scan(started_at, source, tab_label, header_total, uid, app_version) "
            "VALUES (?,?,?,?,?,?)",
            (datetime.now(UTC).isoformat(timespec="seconds"), source, tab_label, header_total,
             uuid.uuid4().hex, this_version()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def add_observations(self, scan_id: int, rows: list[Observation]) -> None:
        self.conn.executemany(
            """INSERT INTO observation
               (scan_id, frame, row, col, icon_hash, rarity, rarity_conf,
                count, count_conf, item_name, needs_review, item_key, rivals,
                level, holder_key)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [
                (
                    scan_id, o.frame, o.row, o.col, o.icon_hash, o.rarity,
                    o.rarity_conf, o.count, o.count_conf, o.item_name, int(o.needs_review),
                    o.item_key, "|".join(o.rivals) or None, o.level, o.holder_key,
                )
                for o in rows
            ],
        )
        self.conn.commit()

    def holder_faces(self, backbone: str | None = None) -> list[sqlite3.Row]:
        """Every portrait seen on a 武器 tile, named or not (D61)."""
        sql = ("SELECT key, name, backbone, embedding, suggestions FROM holder_face "
               "WHERE embedding IS NOT NULL")
        args: tuple = ()
        if backbone is not None:
            sql += " AND backbone = ?"
            args = (backbone,)
        return list(self.conn.execute(sql + " ORDER BY key", args))

    def add_holder_face(
        self, key: str, backbone: str, embedding: bytes, suggestions: tuple[str, ...] = ()
    ) -> bool:
        """Store a portrait the first time it is seen. True when it was new."""
        now = datetime.now(UTC).isoformat(timespec="seconds")
        with self.conn:
            cur = self.conn.execute(
                "INSERT OR IGNORE INTO holder_face"
                "(key, backbone, embedding, created_at, suggestions) VALUES (?,?,?,?,?)",
                (key, backbone, embedding, now, "|".join(suggestions) or None),
            )
        return cur.rowcount > 0

    def set_holder_name(self, key: str, name: str | None) -> None:
        """Name a portrait by hand -- the only way a face is ever named (D61)."""
        now = datetime.now(UTC).isoformat(timespec="seconds")
        with self.conn:
            self.conn.execute(
                "UPDATE holder_face SET name = ?, named_at = ? WHERE key = ?", (name, now, key)
            )

    #: What a scan wrote or learned, and so what "start over" removes (D99).
    #: Everything else is the user's own: targets, plans, where each resonator
    #: stands, the pull history, settings, the dishes already learned.
    SCAN_TABLES = ("observation", "scan", "wallet", "manual_count", "name_alias",
                   "weapon_kind", "holder_face")

    def backup_to(self, dest: Path) -> Path:
        """A consistent copy of the whole database at `dest`."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        self.conn.commit()
        copy = sqlite3.connect(dest)
        try:
            self.conn.backup(copy)
        finally:
            copy.close()
        return dest

    def wipe_scans(self) -> dict[str, int]:
        """Forget every scan and what scans taught; keep what the user set (D99).

        The reference gallery stays -- it is the catalogue, not a scan -- so the
        next scan names items exactly as a fresh install would.
        """
        gone: dict[str, int] = {}
        with self.conn:
            for table in self.SCAN_TABLES:
                gone[table] = self.conn.execute(f"DELETE FROM {table}").rowcount  # noqa: S608
            gone["gallery"] = self.conn.execute(
                "DELETE FROM gallery WHERE tab IS NULL OR tab != 'reference'"
            ).rowcount
            self.conn.execute("DELETE FROM sync_seen")
            self.conn.execute(
                "DELETE FROM sqlite_sequence WHERE name IN ('scan', 'observation', 'wallet')"
            )
            # A scanner that keeps a copy of what scans taught must start over too,
            # or its next upload would bring it all back (D145).
            self.conn.execute(
                "INSERT INTO app_setting(key, value) VALUES (?, '1') "
                "ON CONFLICT(key) DO UPDATE SET value = CAST(value AS INTEGER) + 1",
                (SYNC_EPOCH,),
            )
        self.conn.execute("VACUUM")
        return gone

    def sync_epoch(self) -> int:
        """How many times this database has been started over (`wipe_scans`)."""
        return int(self.setting(SYNC_EPOCH, "0") or 0)

    def learn_weapon_kind(self, name: str, kind: str) -> None:
        """Remember a weapon's type as its own panel printed it (D98)."""
        now = datetime.now(UTC).isoformat(timespec="seconds")
        with self.conn:
            self.conn.execute(
                "INSERT INTO weapon_kind(name, kind, seen_at) VALUES (?,?,?) "
                "ON CONFLICT(name) DO UPDATE SET kind = excluded.kind, seen_at = excluded.seen_at",
                (name, kind, now),
            )

    def weapon_kinds(self) -> dict[str, str]:
        return {r["name"]: r["kind"]
                for r in self.conn.execute("SELECT name, kind FROM weapon_kind")}

    def holder_names(self) -> dict[str, str]:
        return {
            r["key"]: r["name"]
            for r in self.conn.execute(
                "SELECT key, name FROM holder_face WHERE name IS NOT NULL"
            )
        }

    def set_manual_count(self, ident: str, count: int) -> None:
        """A hand-corrected count, the newest reading of `ident` from now (D45)."""
        now = datetime.now(UTC).isoformat(timespec="seconds")
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO manual_count (ident, count, set_at) VALUES (?,?,?)",
                (ident, count, now),
            )

    def manual_counts(self) -> dict[str, tuple[int, str]]:
        with closing(self.conn.execute("SELECT ident, count, set_at FROM manual_count")) as cur:
            return {r[0]: (r[1], r[2]) for r in cur.fetchall()}

    # ------------------------------------------------ main-app settings (D45)

    def setting(self, key: str, default: str | None = None) -> str | None:
        row = self.conn.execute("SELECT value FROM app_setting WHERE key = ?", (key,)).fetchone()
        return row[0] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO app_setting (key, value) VALUES (?,?)", (key, value)
            )

    # ------------------------------------------------------------ 猜谜 (D147)

    @staticmethod
    def _guess_round(row: sqlite3.Row | None) -> dict | None:
        if row is None:
            return None
        return {**dict(row), "guesses": json.loads(row["guesses"]),
                "notes": json.loads(row["notes"])}

    def guess_round(self, mode: str, day: str | None = None) -> dict | None:
        """The daily round of `day`, or the free round last started."""
        if mode == "daily":
            row = self.conn.execute(
                "SELECT * FROM guess_round WHERE mode = 'daily' AND day = ?", (day,)).fetchone()
        else:
            row = self.conn.execute(
                "SELECT * FROM guess_round WHERE mode = 'free' ORDER BY id DESC LIMIT 1").fetchone()
        return self._guess_round(row)

    def guess_rounds(self) -> list[dict]:
        with closing(self.conn.execute("SELECT * FROM guess_round ORDER BY id")) as cur:
            return [self._guess_round(r) for r in cur.fetchall()]

    def start_guess_round(self, mode: str, day: str | None, level: str, answer: str) -> dict:
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO guess_round (mode, day, level, answer, started_at) VALUES (?,?,?,?,?)",
                (mode, day, level, answer, datetime.now(UTC).isoformat(timespec="seconds")))
        row = self.conn.execute("SELECT * FROM guess_round WHERE id = ?", (cur.lastrowid,))
        return self._guess_round(row.fetchone())

    def save_guess_round(self, round_id: int, guesses: list[str], notes: dict[str, str],
                         result: str | None) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE guess_round SET guesses = ?, notes = ?, result = ? WHERE id = ?",
                (json.dumps(guesses, ensure_ascii=False), json.dumps(notes), result, round_id))

    def set_guess_level(self, round_id: int, level: str) -> None:
        """Change the level of a round nobody has guessed in yet."""
        with self.conn:
            self.conn.execute(
                "UPDATE guess_round SET level = ? WHERE id = ? AND guesses = '[]'",
                (level, round_id))

    def drop_guess_round(self, round_id: int) -> None:
        """A free round given up before it was finished: it was never played."""
        with self.conn:
            self.conn.execute("DELETE FROM guess_round WHERE id = ?", (round_id,))

    def material_targets(self) -> dict[str, int]:
        """Targets set by hand on the 材料 page (D84): stock for what is coming."""
        cut = len(MATERIAL_TARGET_PREFIX)
        return {
            r["name"][cut:]: r["target"] for r in self.conn.execute(
                "SELECT name, target FROM craft_target WHERE name LIKE ?",
                (MATERIAL_TARGET_PREFIX + "%",),
            )
        }

    def set_material_target(self, name: str, target: int | None) -> None:
        """None goes back to what the builds ask for."""
        self.set_craft_target(f"{MATERIAL_TARGET_PREFIX}{name}", target)

    def base_amounts(self) -> dict[str, int]:
        """The least to keep of each item the user gave a base amount (D158). The
        echoes' base is not an item's, and is `echo_base`."""
        cut = len(BASE_AMOUNT_PREFIX)
        return {
            r["name"][cut:]: r["target"] for r in self.conn.execute(
                "SELECT name, target FROM craft_target WHERE name LIKE ?",
                (BASE_AMOUNT_PREFIX + "%",),
            ) if r["name"][cut:] != ECHO_BASE
        }

    def echo_base(self) -> int:
        """How many five-star echoes to +25 the 密音筒 owned should be enough for (D161).
        0: none."""
        row = self.conn.execute("SELECT target FROM craft_target WHERE name = ?",
                                (BASE_AMOUNT_PREFIX + ECHO_BASE,)).fetchone()
        return int(row[0]) if row else 0

    def set_base_amount(self, name: str, base: int | None) -> None:
        """None, or nothing, takes the base away: there is no keeping at least 0."""
        self.set_craft_target(f"{BASE_AMOUNT_PREFIX}{name}", base or None)

    def clear_material_targets(self) -> int:
        """Drop every hand-set material target, and say how many there were (D87).

        Only the 材料: rows: the dish targets live in the same table and are not
        part of this.
        """
        with self.conn:
            cur = self.conn.execute(
                "DELETE FROM craft_target WHERE name LIKE ?",
                (MATERIAL_TARGET_PREFIX + "%",),
            )
        return cur.rowcount

    def craft_targets(self) -> dict[str, int]:
        """Dish and potion targets; the material ones (D84) and the base amounts
        (D158) live under prefixes of their own."""
        with closing(self.conn.execute("SELECT name, target FROM craft_target")) as cur:
            return {r[0]: r[1] for r in cur.fetchall()
                    if not r[0].startswith((MATERIAL_TARGET_PREFIX, BASE_AMOUNT_PREFIX))}

    def set_craft_target(self, name: str, target: int | None) -> None:
        """A per-item target; None goes back to the type's default."""
        with self.conn:
            if target is None:
                self.conn.execute("DELETE FROM craft_target WHERE name = ?", (name,))
            else:
                self.conn.execute(
                    "INSERT OR REPLACE INTO craft_target (name, target) VALUES (?,?)",
                    (name, target),
                )

    def learned_recipes(self) -> set[str]:
        with closing(self.conn.execute("SELECT name FROM learned_recipe")) as cur:
            return {r[0] for r in cur.fetchall()}

    def set_learned(self, name: str, learned: bool) -> None:
        with self.conn:
            if learned:
                self.conn.execute("INSERT OR IGNORE INTO learned_recipe (name) VALUES (?)", (name,))
            else:
                self.conn.execute("DELETE FROM learned_recipe WHERE name = ?", (name,))

    # ------------------------------------------------------------ wallet (D48)

    def add_wallet(self, shells: int | None, astrite: int | None, confidence: float) -> None:
        """Keep a reading when it says something new (the bar is re-read per tab)."""
        last = self.wallet()
        if last and (last["shells"], last["astrite"]) == (shells, astrite):
            return
        with self.conn:
            self.conn.execute(
                "INSERT INTO wallet (read_at, shells, astrite, confidence) VALUES (?, ?, ?, ?)",
                (datetime.now(UTC).isoformat(timespec="seconds"), shells, astrite, confidence),
            )

    def wallet(self) -> dict | None:
        """The newest reading: {shells, astrite, read_at, confidence} or None.

        Each amount is its own newest reading (D198): a view that read 贝币 and missed 星声
        does not make 星声 nothing -- 总览 said 0 where the reading before said 79.
        `astrite_read_at` / `shells_read_at` say when an amount older than the reading was read."""
        row = self.conn.execute(
            "SELECT read_at, shells, astrite, confidence FROM wallet ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        said = dict(row)
        for amount in ("shells", "astrite"):
            if said[amount] is None:
                older = self.conn.execute(
                    f"SELECT {amount}, read_at FROM wallet WHERE {amount} IS NOT NULL "  # noqa: S608
                    "ORDER BY id DESC LIMIT 1").fetchone()
                if older is not None:
                    said[amount], said[f"{amount}_read_at"] = older[0], older[1]
        return said

    # --------------------------------------------------- resonator state (D50)

    def progress(self) -> dict[str, dict]:
        """name -> {"owned": bool, "state": {...}} for every resonator the user set."""
        with closing(
            self.conn.execute("SELECT name, owned, state, chain FROM resonator_state")
        ) as cur:
            return {r["name"]: {"owned": bool(r["owned"]), "state": json.loads(r["state"]),
                                "chain": r["chain"]}
                    for r in cur.fetchall()}

    def set_progress(
        self, name: str, owned: bool, state: dict, chain: int | None = None
    ) -> None:
        """`chain` (共鸣链) is set by hand and kept: a pull export cannot see the
        copies that came free or in a top-up pack (D69). None leaves it alone."""
        with self.conn:
            self.conn.execute(
                "INSERT INTO resonator_state (name, owned, state, chain, updated_at) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(name) DO UPDATE SET owned=excluded.owned, state=excluded.state, "
                "chain=COALESCE(excluded.chain, resonator_state.chain), "
                "updated_at=excluded.updated_at",
                (name, int(owned), json.dumps(state, ensure_ascii=False), chain,
                 datetime.now(UTC).isoformat(timespec="seconds")),
            )

    def set_chain(self, name: str, chain: int | None) -> None:
        """Set 共鸣链 alone, for a resonator with no saved progress yet."""
        now = datetime.now(UTC).isoformat(timespec="seconds")
        with self.conn:
            self.conn.execute(
                "INSERT INTO resonator_state (name, owned, state, chain, updated_at) "
                "VALUES (?, 1, '{}', ?, ?) "
                "ON CONFLICT(name) DO UPDATE SET chain=excluded.chain, "
                "owned=CASE WHEN excluded.chain IS NULL THEN resonator_state.owned ELSE 1 END, "
                "updated_at=excluded.updated_at",
                (name, chain, now),
            )

    def set_owned(self, name: str, owned: bool) -> None:
        """Say by hand that a resonator is (or is not) on the account (D116).

        For the ones no pull shows: given away, bought in a shop, in a pack. The
        level and skills saved for them are left alone. Saying "not owned" also
        drops a 共鸣链 set by hand -- a chain belongs to someone you have -- and
        a row that then says nothing at all is removed rather than kept empty.
        """
        now = datetime.now(UTC).isoformat(timespec="seconds")
        with self.conn:
            self.conn.execute(
                "INSERT INTO resonator_state (name, owned, state, chain, updated_at) "
                "VALUES (?, ?, '{}', NULL, ?) "
                "ON CONFLICT(name) DO UPDATE SET owned=excluded.owned, "
                "chain=CASE WHEN excluded.owned=1 THEN resonator_state.chain ELSE NULL END, "
                "updated_at=excluded.updated_at",
                (name, int(owned), now),
            )
            if not owned:
                self.conn.execute(
                    "DELETE FROM resonator_state WHERE name = ? AND owned = 0 AND state = '{}'",
                    (name,),
                )

    def clear_progress(self, name: str) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM resonator_state WHERE name = ?", (name,))

    # -------------------------------------------------------- pull import (D53)

    def set_pulls(self, data: dict) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM pull_import")
            self.conn.execute("INSERT INTO pull_import (imported_at, data) VALUES (?, ?)",
                              (datetime.now(UTC).isoformat(timespec="seconds"),
                               json.dumps(data, ensure_ascii=False)))

    def pulls(self) -> dict | None:
        row = self.conn.execute(
            "SELECT imported_at, data FROM pull_import ORDER BY id DESC LIMIT 1").fetchone()
        return {**json.loads(row["data"]), "imported_at": row["imported_at"]} if row else None

    # ----------------------------------------------------------- planner (D47)

    def plans(self) -> list[dict]:
        with closing(self.conn.execute(
            "SELECT id, kind, name, state FROM plan ORDER BY position, id"
        )) as cur:
            return [{"id": r["id"], "kind": r["kind"], "name": r["name"],
                     **json.loads(r["state"])} for r in cur.fetchall()]

    def add_plan(self, kind: str, name: str, state: dict) -> int:
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO plan (kind, name, state, position, created_at) VALUES "
                "(?, ?, ?, (SELECT COALESCE(MAX(position), 0) + 1 FROM plan), ?)",
                (kind, name, json.dumps(state, ensure_ascii=False),
                 datetime.now(UTC).isoformat(timespec="seconds")),
            )
            return int(cur.lastrowid)

    def set_plan_state(self, plan_id: int, state: dict) -> bool:
        with self.conn:
            cur = self.conn.execute("UPDATE plan SET state = ? WHERE id = ?",
                                    (json.dumps(state, ensure_ascii=False), plan_id))
            return cur.rowcount > 0

    def remove_plan(self, plan_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM plan WHERE id = ?", (plan_id,))

    def item_crops(self, scan_id: int, item_key: str) -> list[str]:
        """Every distinct crop hash one stitched item was seen as in a scan."""
        with closing(
            self.conn.execute(
                "SELECT DISTINCT icon_hash FROM observation WHERE scan_id=? AND item_key=?",
                (scan_id, item_key),
            )
        ) as cur:
            return [r[0] for r in cur.fetchall()]

    def name_item(self, scan_id: int, item_key: str, name: str) -> int:
        """Name an item nobody has named yet, by hand (D65).

        `add_alias` corrects a name that exists; this gives one to an item that
        has none. The crops go into the gallery under that name too, so the next
        scan knows it without being told again -- which is how a weapon the
        catalogue has no artwork for (奇幻变奏) ever gets recognised.
        """
        crops = self.item_crops(scan_id, item_key)
        with self.conn:
            rows = self.conn.execute(
                "UPDATE observation SET item_name = ? WHERE scan_id = ? AND item_key = ?",
                (name, scan_id, item_key),
            ).rowcount
            if crops:
                marks = ",".join("?" * len(crops))
                rows += self.conn.execute(
                    f"UPDATE gallery SET item_name = ? WHERE icon_hash IN ({marks})",  # noqa: S608
                    (name, *crops),
                ).rowcount
                rows += self._rename_lookalikes(crops, name)
        return rows

    #: How alike two crops must be to be the same picture (D165): crops of one tile across
    #: frames scored 0.9998 and up; the look-alike sword beside it, 0.81.
    SAME_PICTURE = 0.97

    def _rename_lookalikes(self, crops: list[str], name: str | None) -> int:
        """Crops learned elsewhere that are the same picture as `crops` take their name (D165).

        A crop named wrongly once (a panel credited to the tile beside it) is matched exactly
        by every scan after; naming the tile by hand puts its crops right, and with them every
        crop of the same picture learned before, from scans this machine may not even have.
        The catalogue's own icons are never touched."""
        same = self.same_picture(crops, unless=name)
        for digest in same:
            self.conn.execute("UPDATE gallery SET item_name = ? WHERE icon_hash = ?",
                              (name, digest))
        return len(same)

    def same_picture(self, crops: list[str], unless: str | None = None) -> list[str]:
        """Learned crops, besides `crops`, that are the same picture as one of them (D165):
        cosine >= SAME_PICTURE, the same encoder; not the catalogue's, and not already `unless`."""
        if not crops:
            return []
        marks = ",".join("?" * len(crops))
        mine = self.conn.execute(
            f"SELECT backbone, embedding FROM gallery WHERE icon_hash IN ({marks}) "  # noqa: S608
            "AND embedding IS NOT NULL", crops).fetchall()
        same: list[str] = []
        for backbone, blob in {(r[0], r[1]) for r in mine}:
            ref = np.frombuffer(blob, dtype=np.float32)
            ref = ref / max(float(np.linalg.norm(ref)), 1e-12)
            others = self.conn.execute(
                "SELECT icon_hash, embedding FROM gallery WHERE backbone = ? "
                "AND embedding IS NOT NULL AND (tab IS NULL OR tab != 'reference') "
                f"AND item_name IS NOT ? "  # noqa: S608
                f"AND icon_hash NOT IN ({marks})", (backbone, unless, *crops)).fetchall()
            for digest, other in others:
                vec = np.frombuffer(other, dtype=np.float32)
                norm = max(float(np.linalg.norm(vec)), 1e-12)
                if digest not in same and vec.shape == ref.shape \
                        and float(ref @ vec) / norm >= self.SAME_PICTURE:
                    same.append(digest)
        return same

    def learned_crop(self, icon_hash: str) -> bool:
        """Is this a picture saved from the game (not the catalogue's own)? (D166)"""
        return self.conn.execute(
            "SELECT 1 FROM gallery WHERE icon_hash = ? AND (tab IS NULL OR tab != 'reference')",
            (icon_hash,)).fetchone() is not None

    def rename_crop(self, icon_hash: str, name: str | None) -> dict:
        """Give a learned picture a new name, or none (D166): it, every crop of the same picture,
        and every scan's row that saw one of them. Returns how many of each changed."""
        with self.conn:
            crops = [icon_hash, *self.same_picture([icon_hash], unless=name)]
            marks = ",".join("?" * len(crops))
            changed = self.conn.execute(
                f"UPDATE gallery SET item_name = ? WHERE icon_hash IN ({marks}) "  # noqa: S608
                "AND (tab IS NULL OR tab != 'reference')", (name, *crops)).rowcount
            rows = self.conn.execute(
                f"UPDATE observation SET item_name = ? WHERE icon_hash IN ({marks})",  # noqa: S608
                (name, *crops)).rowcount
        return {"crops": changed, "rows": rows}

    def confirm_crop(self, icon_hash: str) -> dict | None:
        """Say a learned picture's name is right although the catalogue doubts it (D167): it and
        every crop of the same picture under that name. None when it is not a named, learned
        picture."""
        row = self.conn.execute(
            "SELECT item_name FROM gallery WHERE icon_hash = ? AND item_name IS NOT NULL "
            "AND (tab IS NULL OR tab != 'reference')", (icon_hash,)).fetchone()
        if row is None:
            return None
        name = row[0]
        others = self.same_picture([icon_hash])
        if others:
            marks = ",".join("?" * len(others))
            others = [r[0] for r in self.conn.execute(
                f"SELECT icon_hash FROM gallery WHERE icon_hash IN ({marks}) "  # noqa: S608
                "AND item_name = ?", (*others, name))]
        crops = [icon_hash, *others]
        at = datetime.now(UTC).isoformat(timespec="seconds")
        with self.conn:
            self.conn.executemany(
                "INSERT OR REPLACE INTO crop_confirmed (icon_hash, name, at) VALUES (?, ?, ?)",
                [(c, name, at) for c in crops])
        return {"crops": len(crops), "name": name}

    def confirmed_crops(self) -> dict[str, str]:
        """Learned pictures said to be rightly named (D167): hash -> the name they were confirmed
        under."""
        return dict(self.conn.execute("SELECT icon_hash, name FROM crop_confirmed").fetchall())

    def forget_item(self, scan_id: int, item_key: str) -> int:
        """Drop a tile that is not an item at all (D66).

        Tile detection sometimes catches a fragment mid-animation: one such
        phantom made a 资源 scan read 116 of 115. Nothing can name it, so the
        user says so, and both its sightings and its crops go -- a crop left in
        the gallery would keep being "recognised" in later scans.
        """
        crops = self.item_crops(scan_id, item_key)
        with self.conn:
            rows = self.conn.execute(
                "DELETE FROM observation WHERE scan_id = ? AND item_key = ?", (scan_id, item_key)
            ).rowcount
            if crops:
                marks = ",".join("?" * len(crops))
                rows += self.conn.execute(
                    f"DELETE FROM gallery WHERE icon_hash IN ({marks}) "  # noqa: S608
                    "AND item_name IS NULL AND tab != 'reference'",
                    tuple(crops),
                ).rowcount
        return rows

    def aliases(self) -> dict[str, str]:
        """User name corrections: misread name -> real name."""
        with closing(self.conn.execute("SELECT wrong, right FROM name_alias")) as cur:
            return {r[0]: r[1] for r in cur.fetchall()}

    def add_alias(self, wrong: str, right: str) -> int:
        """Record a name correction and apply it to everything already stored.

        Returns how many gallery entries and observations were renamed. An alias
        that pointed AT `wrong` is repointed, so chains never form.
        """
        now = datetime.now(UTC).isoformat(timespec="seconds")
        with self.conn:
            self.conn.execute("DELETE FROM name_alias WHERE wrong = ?", (right,))
            self.conn.execute("UPDATE name_alias SET right = ? WHERE right = ?", (right, wrong))
            self.conn.execute(
                "INSERT OR REPLACE INTO name_alias (wrong, right, created_at) VALUES (?,?,?)",
                (wrong, right, now),
            )
            g = self.conn.execute(
                "UPDATE gallery SET item_name = ? WHERE item_name = ?", (right, wrong)
            ).rowcount
            o = self.conn.execute(
                "UPDATE observation SET item_name = ? WHERE item_name = ?", (right, wrong)
            ).rowcount
        return g + o

    def finish_scan(self, scan_id: int, frames: int, tiles: int, complete: bool) -> None:
        self.conn.execute(
            "UPDATE scan SET frame_count=?, tile_count=?, complete=? WHERE id=?",
            (frames, tiles, int(complete), scan_id),
        )
        self.conn.commit()

    def copy_observations(self, from_scan: int, to_scan: int) -> int:
        """Carry one scan's rows into another (D173): a tab come back to goes on under a new
        scan number with what was read before."""
        columns = [r[1] for r in self.conn.execute("PRAGMA table_info(observation)")
                   if r[1] not in ("id", "scan_id")]
        with self.conn:
            return self.conn.execute(
                f"INSERT INTO observation (scan_id, {', '.join(columns)}) "  # noqa: S608
                f"SELECT ?, {', '.join(columns)} FROM observation WHERE scan_id = ? ORDER BY id",
                (to_scan, from_scan)).rowcount

    def latest_scan(self) -> sqlite3.Row | None:
        with closing(self.conn.execute("SELECT * FROM scan ORDER BY id DESC LIMIT 1")) as cur:
            return cur.fetchone()

    def scan(self, scan_id: int) -> sqlite3.Row | None:
        with closing(self.conn.execute("SELECT * FROM scan WHERE id = ?", (scan_id,))) as cur:
            return cur.fetchone()

    def latest_scans_by_tab(self) -> list[sqlite3.Row]:
        """The newest scan of every tab, with how many distinct items it found.

        One live session writes one scan per tab, so "the latest scan" alone showed
        only the tab visited last -- 补给 and 素材, both complete, were invisible.
        """
        with closing(
            self.conn.execute(
                """SELECT s.*, (SELECT COUNT(DISTINCT COALESCE(o.item_key, o.icon_hash))
                                  FROM observation o WHERE o.scan_id = s.id) AS found
                     FROM scan s
                    WHERE s.id IN (SELECT MAX(id) FROM scan
                                    WHERE tab_label IS NOT NULL GROUP BY tab_label)
                 ORDER BY s.id DESC"""
            )
        ) as cur:
            return cur.fetchall()

    def observations(self, scan_id: int) -> list[sqlite3.Row]:
        with closing(
            self.conn.execute(
                "SELECT * FROM observation WHERE scan_id=? ORDER BY row, col", (scan_id,)
            )
        ) as cur:
            return cur.fetchall()

    def unique_items(self, scan_id: int) -> list[sqlite3.Row]:
        """One row per stitched item, keeping the highest-confidence count.

        Grouped by `item_key` (the stitcher's identity), falling back to icon hash
        for scans recorded before v3. Grouping by hash alone overcounted a live
        scan 185 vs the game's 170 while only ~68 items had actually been seen.
        """
        with closing(
            self.conn.execute(
                """SELECT COALESCE(item_key, icon_hash)       AS icon_hash, rarity,
                          MAX(count_conf)                      AS best_conf,
                          (SELECT count FROM observation o2
                            WHERE COALESCE(o2.item_key, o2.icon_hash)
                                  = COALESCE(o1.item_key, o1.icon_hash)
                              AND o2.scan_id = o1.scan_id
                            ORDER BY count_conf DESC LIMIT 1)  AS count,
                          MAX(item_name)                       AS item_name,
                          COUNT(*)                             AS seen
                     FROM observation o1
                    WHERE scan_id = ?
                 GROUP BY COALESCE(item_key, icon_hash)
                 ORDER BY rarity DESC, count DESC""",
                (scan_id,),
            )
        ) as cur:
            return cur.fetchall()
