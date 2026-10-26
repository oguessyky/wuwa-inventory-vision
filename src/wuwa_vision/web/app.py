# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""The local web apps (PLAN.md D5, D25, D45).

Two separate apps on two ports, so a scan and the main app never get in each
other's way (D45 decision 2):

* the SCAN MONITOR, served by `wuwa live` on 8711 -- the live page and its API;
* the MAIN APP, served by `wuwa serve` on 4000 -- inventory, cooking, materials,
  resonators, weapons, the catalogue update page (and later the planner).

Both bind 127.0.0.1 only -- zero egress is a hard constraint, not a default. The
one exception is the 更新 page's button (D46): the user clicks it to run the
catalogue setup tools, which fetch from Kuro's wiki. The
logic lives in the headless core (inventory, catalogue); these are thin clients.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import threading
import urllib.parse
import time
from collections.abc import Callable
from contextvars import ContextVar
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import DEFAULT_EXCLUDED_CONTENT_TYPES, GZipMiddleware
from pydantic import BaseModel, Field

from .. import dashboard as dashboard_mod
from .. import demo, exp, guess, planner, roster
from .. import shops as shops_mod
from .. import weapons as weapons_mod
from ..catalogue import Catalogue, read_overrides, write_overrides
from ..cooking import CRAFT_TAB, TYPES, build_cooking, default_targets, ingredient_sources
from ..inventory import build_inventory, tab_summary
from ..materials import (
    CURRENCY,
    PRESETS,
    build_materials,
    families,
    family,
    preset,
    reasons,
    role_of,
    rover_only,
    slot_of,
    typical,
    users,
)
from ..recognize.names import WEAPON_TAB
from ..recognize.reference import name_to_file, reference_dir
from ..scan.live_state import LiveState, needs_you
from ..store.db import Store
from ..update import UpdateJob

#: The scan monitor's page (`live.html`): hand-written, and not part of the build.
STATIC = Path(__file__).parent / "static"
LIVE_PORT, MAIN_PORT = 8711, 4000
#: The phone's page (`phone.html`, D153): what `wuwa live --share` gives the tailnet.
PHONE_PORT = 8713
#: A pull export is ~1 MB for 4,500 pulls; this leaves room for years of pulls.
MAX_PULLS_BYTES = 20_000_000


class NameFix(BaseModel):
    """A user's correction of a misread item name (D40)."""

    wrong: str = Field(min_length=1, max_length=64)
    right: str = Field(min_length=1, max_length=64)


class CountFix(BaseModel):
    """A count corrected by hand (D45): the item's newest reading until rescanned."""

    ident: str = Field(min_length=1, max_length=80)
    count: int = Field(ge=0, le=10_000_000)


class TargetFix(BaseModel):
    """A dish/potion's stock target; None goes back to its type's default (D45)."""

    name: str = Field(min_length=1, max_length=80)
    target: int | None = Field(default=None, ge=0, le=100_000)


class MaterialPreset(BaseModel):
    """A stock-up set for a material's whole family (D88); None resets the family."""

    name: str = Field(min_length=1, max_length=80)
    preset: str | None = None


class DefaultTarget(BaseModel):
    type: str
    target: int = Field(ge=0, le=100_000)


class Learned(BaseModel):
    """A 食谱/配方 ticked (or unticked) as learned (D45 decision 7)."""

    recipe: str = Field(min_length=1, max_length=80)
    learned: bool


class ItemOverride(BaseModel):
    """A material added or fixed by hand (更新 page, D46)."""

    name: str = Field(min_length=1, max_length=40)
    rarity: int = Field(ge=1, le=5)
    tab: str = Field(default="素材", max_length=10)
    类型: str = Field(default="", max_length=40)
    功能: str = Field(default="", max_length=200)
    获取途径: str = Field(default="", max_length=400)


class FamilyOverride(BaseModel):
    """A material family set by hand: its members, lowest tier first."""

    names: list[str] = Field(min_length=2, max_length=6)


class WeaponOverride(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    type: str = Field(min_length=1, max_length=10)
    rarity: int = Field(ge=1, le=5)
    materials: dict[str, int] = Field(default_factory=dict)


class ResonatorOverride(BaseModel):
    """A resonator's 练满材料 filled in by hand (D74), for one the wiki has none
    for yet. Only the fields given are written over what the catalogue has."""

    name: str = Field(min_length=1, max_length=40)
    element: str = Field(default="", max_length=10)
    weapon: str = Field(default="", max_length=10)
    rarity: int = Field(default=5, ge=1, le=5)
    materials: dict[str, int] = Field(default_factory=dict)


class SignatureFix(BaseModel):
    """A resonator's 专武 set by hand (D46); None clears it, "" means "has none"."""

    resonator: str = Field(min_length=1, max_length=40)
    weapon: str | None = Field(default=None, max_length=40)


class ItemForget(BaseModel):
    """A tile that is not an item at all (D66)."""

    scan_id: int
    key: str = Field(min_length=8, max_length=64, pattern=r"^[0-9a-f]+$")


class CropName(BaseModel):
    """A learned picture's new name, or none (D166, 更新 › 识别)."""

    hash: str = Field(min_length=1, max_length=64)
    name: str | None = Field(default=None, max_length=40)


class ItemName(BaseModel):
    """A name for an item nobody has named yet (D65)."""
    scan_id: int
    key: str = Field(min_length=8, max_length=64, pattern=r"^[0-9a-f]+$")
    name: str = Field(min_length=1, max_length=40)


class HolderName(BaseModel):
    """Who a 武器 tile's portrait is (D61); an empty name forgets it."""

    key: str = Field(min_length=8, max_length=64, pattern=r"^[0-9a-f]+$")
    name: str | None = Field(default=None, max_length=40)


class Progress(BaseModel):
    """Where one resonator stands (D50); state None forgets it."""

    name: str = Field(min_length=1, max_length=40)
    owned: bool = True
    state: dict | None = None


class BulkProgress(BaseModel):
    """Several resonators marked at once (D59, D194): 已练满, 已拥有, or forgotten."""

    names: list[str] = Field(min_length=1, max_length=200)
    how: Literal["max", "owned", "clear"]


class RoverGender(BaseModel):
    """Which 漂泊者 this save has (D72)."""

    gender: str = Field(pattern="^(女|男)$")


class GuessLevel(BaseModel):
    """猜谜: the level the next round is played at (D147)."""

    mode: str = Field(pattern="^(daily|free)$")
    level: str = Field(max_length=8)


class GuessTry(BaseModel):
    """猜谜: one guess."""

    mode: str = Field(pattern="^(daily|free)$")
    name: str = Field(min_length=1, max_length=40)


class GuessNote(BaseModel):
    """猜谜: the player's own mark on one cell of a 噩梦 row; None clears it."""

    mode: str = Field(pattern="^(daily|free)$")
    row: int = Field(ge=0, lt=16)
    column: str = Field(max_length=16)
    mark: str | None = Field(default=None, max_length=8)


class GuessNew(BaseModel):
    """猜谜: another free round."""

    mode: str = Field(pattern="^free$")


class Owned(BaseModel):
    """A resonator marked owned (or not) by hand (D116)."""

    name: str = Field(min_length=1, max_length=40)
    owned: bool


class Chain(BaseModel):
    """共鸣链 set by hand (D69); None goes back to whatever the pulls say."""

    name: str = Field(min_length=1, max_length=40)
    chain: int | None = Field(default=None, ge=0, le=6)


class EnglishFix(BaseModel):
    """A name's English name, given by hand on the 更新 page (D163); None takes it away."""

    name: str = Field(min_length=1, max_length=80)
    english: str | None = Field(default=None, max_length=120)


class BaseFix(BaseModel):
    """The same base amount for several things a shop sells at once (D160)."""

    names: list[str] = Field(min_length=1, max_length=400)
    target: int | None = Field(default=None, ge=0, le=100_000)


class PlanNew(BaseModel):
    kind: str
    name: str = Field(min_length=1, max_length=40)


class PlanState(BaseModel):
    """A plan's two states (D47); the core clamps them to what exists."""

    current: dict
    target: dict


class Removal(BaseModel):
    kind: str
    key: str


class UpdateStart(BaseModel):
    seed: bool = False


class PullName(BaseModel):
    """One pull id and the name the user gives it ("" takes the name back)."""

    gid: str
    name: str = ""


#: builds.json art: "<entry id>.webp" / "<entry id>.card.webp", nothing else.
_ART_FILE = re.compile(r"^\d{1,24}(\.card)?\.webp$")
#: avatars/ (tools/fetch_icons.py): "r-23654.webp", "el-rerong.webp", "coin.webp".
_AVATAR_FILE = re.compile(r"^[a-z0-9-]{1,48}\.(webp|png)$")
#: The weapon-type icons the app ships (catalogue.WEAPON_TYPE_ICONS): "wp-sword.svg".
ICONS = STATIC / "icons"
#: The markers of each kind of shop the app ships (D161): "shop-grocer.webp".
SHOP_MARKERS = frozenset(f"shop-{kind}.webp" for kind in (
    "grocer", "diner", "pharmacy", "forge", "exchange", "general"))
#: The pictures of 更新's parts the app ships (D162), white on clear, drawn in the
#: colour of their link: "upd-wiki.png".
#: 更新's parts, each at an address of its own (D164): /update/wiki.
UPDATE_PARTS = ("wiki", "mine", "hand", "english", "recognized", "data")
#: The pages besides 总览, by their addresses: /inventory, and /en/inventory in English (D164).
PAGE_NAMES = ("inventory", "shops", "cooking", "materials", "resonators", "weapons", "planner",
              "update", "guess", "about", "help", "privacy")
PART_ICONS = frozenset(f"upd-{part}.png"
                       for part in ("wiki", "hand", "english", "recognized", "data"))
# and the language button's two cards and the card's outline (D164), drawn with Gemini too
PART_ICONS |= {"lang-a.png", "lang-zh.png", "lang-card.png"}


def create_app(db_path: Path, live: LiveState | None = None,
               home_key: str | None = None) -> FastAPI:
    """The scan monitor when `live` is given (inside `wuwa live`), else the main app.

    `home_key`: this app is a home (D145) -- scanners fetch from it, and upload to
    it with this key. Without one it takes no uploads at all."""
    if live is not None:
        return _monitor_app(db_path, live)
    return _main_app(db_path, home_key)


#: Whether this request asked for the walk's sample data (D162).
_SAMPLE: ContextVar[bool] = ContextVar("sample", default=False)
#: The page's language (D164): an English page sends `X-Lang: en`, and the server's own
#: messages to a person -- an error's `detail` -- are then in English.
_ENGLISH: ContextVar[bool] = ContextVar("english", default=False)


def _said(zh: str, en: str) -> str:
    """A message to a person, in the language of the page that asked."""
    return en if _ENGLISH.get() else zh

#: The main app's pages: the Next.js build (`web/`, D105-D107), published into the
#: package as plain files by `npm run build`. No Node is involved in serving them.
UI = Path(__file__).parent / "ui"
#: The project's root, where its licence, terms and privacy policy are (and, in the
#: NAS image, where the Dockerfile puts them).
PROJECT = Path(__file__).resolve().parents[3]
#: The privacy policy (D162): English, which is binding, and a translation for reference.
PRIVACY = {"en": "PRIVACY.md", "zh-CN": "PRIVACY.zh-CN.md"}


def _version() -> str | None:
    """Which build this is, as a NAS bundle's or a release's VERSION says ("v1.0.0  081a452
    2026-10-20 12:45", tools/make_nas_bundle.py); None where there is no such file (a checkout)."""
    path = PROJECT / "VERSION"
    return path.read_text(encoding="utf-8").strip() or None if path.is_file() else None


def _page(name: str) -> HTMLResponse:
    """A page of the main app. Revalidated on every load, so a rebuilt page is
    picked up at once; the scripts and styles it names are hashed and can be kept."""
    page = UI / name
    if not page.is_file():
        raise HTTPException(503, "the pages are not built: run `npm run build` in web/")
    return HTMLResponse(page.read_text(encoding="utf-8"), headers={"Cache-Control": "no-cache"})


def _shared_routes(app: FastAPI, db_path: Path, live: LiveState | None) -> None:
    """What both apps need: name fixes and scanned crops."""

    @app.post("/api/names")
    def fix_name(fix: NameFix) -> dict:
        """Correct a name everywhere, now and for every later read of the misread.

        JSON body only: a cross-site page cannot send application/json to this
        127.0.0.1 server without a CORS preflight, which it does not answer.
        """
        wrong, right = fix.wrong.strip(), fix.right.strip()
        if not wrong or not right or wrong == right:
            raise HTTPException(400, "nothing to change")
        st = Store(db_path)
        try:
            renamed = st.add_alias(wrong, right)
        finally:
            st.close()
        if live is not None:
            live.rename(wrong, right)
        return {"wrong": wrong, "right": right, "renamed": renamed}

    _icon_route(app, db_path)


def _icon_route(app: FastAPI, db_path: Path) -> None:
    """A scanned tile's crop, by its content hash."""

    @app.get("/api/icon/{digest}.webp")
    def icon(digest: str) -> FileResponse:
        if not digest.isalnum():
            raise HTTPException(400, "bad digest")
        # Path only -- no Store: opening one writes schema metadata, which would
        # contend with a live scan writing to the same database.
        path = Path(db_path).parent / "icons" / f"{digest}.webp"
        if not path.exists():
            raise HTTPException(404, "no such icon")
        return FileResponse(path, media_type="image/webp")


# ------------------------------------------------------------ scan monitor


def _monitor_app(db_path: Path, live: LiveState) -> FastAPI:
    app = FastAPI(title="WuWa Inventory Vision -- scan monitor", docs_url="/api/docs")
    _shared_routes(app, db_path, live)

    @app.get("/", response_class=HTMLResponse)
    @app.get("/live", response_class=HTMLResponse)
    def live_page() -> HTMLResponse:
        # The monitor's one page is hand-written and self-contained: no build.
        return HTMLResponse((STATIC / "live.html").read_text(encoding="utf-8"),
                            headers={"Cache-Control": "no-cache"})

    @app.get("/api/live")
    def live_state() -> dict:
        live.asked()  # the page is open: this is what a goodbye is weighed against
        return live.snapshot()

    @app.post("/api/live/bye", status_code=204)
    def live_bye() -> Response:
        """The page is being closed (D156): `wuwa live` need not wait for Enter
        once the scan is over. It takes nothing and changes nothing stored; a
        page that is still open simply asks again (`LiveState.page_gone`)."""
        live.bye()
        return Response(status_code=204)

    @app.get("/api/live/frame.jpg")
    def live_frame() -> Response:
        # Already cropped to the tile grid by LiveState: no UID, no friend names.
        jpeg = live.jpeg()
        if jpeg is None:
            raise HTTPException(404, "no view read yet")
        return Response(jpeg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    @app.get("/api/live/stream.mjpg")
    def live_stream() -> StreamingResponse:
        """The game grid as it is now, ~8 fps (MJPEG: an <img> plays it as video).

        Same crop as frame.jpg -- the grid only, located by the last read view.
        """

        def frames():  # noqa: ANN202 -- generator
            seq = 0
            while True:
                seq, jpeg = live.next_preview(seq, timeout=1.0)
                if jpeg is None:
                    continue
                head = b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                yield head + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n"

        return StreamingResponse(
            frames(), media_type="multipart/x-mixed-replace; boundary=frame",
            headers={"Cache-Control": "no-store"},
        )

    return app


def create_phone_app(db_path: Path, live: LiveState) -> FastAPI:
    """The scan monitor as a phone may have it (D153): looked at, never written to.

    `wuwa live --share` hands this app's port to the user's tailnet, and only
    this one. Behind Tailscale's proxy every request comes from 127.0.0.1, so
    the monitor could not tell a phone from this PC: what a phone must not
    reach is therefore not here at all. No name fix, no picture of the game
    (whatever `--preview` says), nothing but GET.
    """
    app = FastAPI(title="WuWa Inventory Vision -- scan status",
                  docs_url=None, redoc_url=None, openapi_url=None)
    _icon_route(app, db_path)

    @app.get("/", response_class=HTMLResponse)
    def phone_page() -> HTMLResponse:
        return HTMLResponse((STATIC / "phone.html").read_text(encoding="utf-8"),
                            headers={"Cache-Control": "no-cache"})

    @app.get("/api/live")
    def live_state(since: int = -1) -> dict:
        """The monitor's state, or a few bytes when the page already has it: a
        phone asks over the tailnet, perhaps on mobile data."""
        snap = live.snapshot()
        if snap["version"] == since:
            # the sync with the home moves ten times a second and is not a new
            # version of anything (D156): it rides along, a few bytes, while there is one
            return {"version": since, "same": True,
                    **({"sync": snap["sync"]} if snap["sync"] else {})}
        return {**snap, "picture": False, "has_frame": False, "has_preview": False,
                "needs": needs_you(snap)}

    return app


# ---------------------------------------------------------------- main app


#: How often, at most, the catalogue's files are looked at to see whether a setup tool
#: rewrote them (D171). On the user's NAS each look cost 30-90 ms, nine files a look, and
#: some pages asked for the catalogue several times.
CATALOGUE_LOOK = 5.0
_monotonic = time.monotonic


def _mtime(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except OSError:
        return None


class _CatalogueCache:
    """The catalogue, reloaded when a setup tool rewrites its files -- looked for at most
    every CATALOGUE_LOOK seconds, and at once after this app wrote something (`forget`)."""

    def __init__(self) -> None:
        self._stamp: tuple | None = None
        self._catalogue: Catalogue | None = None
        self._looked = float("-inf")
        self.version = 0

    def forget(self) -> None:
        """Look again on the next call: this app may just have written the catalogue."""
        self._looked = float("-inf")

    def get(self) -> Catalogue:
        from ..catalogue import CATALOGUE_DIR

        now = _monotonic()
        if self._catalogue is not None and now - self._looked < CATALOGUE_LOOK:
            return self._catalogue
        self._looked = now
        stamp = tuple(
            _mtime(p)                       # one question per file, not two (D171)
            for p in (CATALOGUE_DIR / "index.json", CATALOGUE_DIR / "recipes.json",
                      CATALOGUE_DIR / "builds.json", CATALOGUE_DIR / "overrides.json",
                      CATALOGUE_DIR / "avatars.json", CATALOGUE_DIR / "bosses.json",
                      CATALOGUE_DIR / "levels.json", CATALOGUE_DIR / "shops.json",
                      CATALOGUE_DIR / "english.json")
        )
        if self._catalogue is None or stamp != self._stamp:
            self._catalogue, self._stamp = Catalogue.load(), stamp
            self.version += 1
        return self._catalogue


class _DataStamp:
    """Which state the database is in, for keeping answers (D171): a count of the writes this
    app made, and the database files' times, looked at at most every CATALOGUE_LOOK seconds --
    the scanner on the PC (`wuwa live`) writes from a process of its own."""

    def __init__(self, path: Path) -> None:
        self._files = (path, path.with_name(path.name + "-wal"))
        self._writes = 0
        self._stamp: tuple = ()
        self._looked = float("-inf")

    def wrote(self) -> None:
        self._writes += 1
        self._looked = float("-inf")

    def get(self) -> tuple:
        now = _monotonic()
        if now - self._looked >= CATALOGUE_LOOK:
            self._looked = now
            self._stamp = tuple(_mtime(p) for p in self._files)
        return (self._writes, self._stamp)


#: The answers that are kept until the database or the catalogue changes (D171): each a
#: function of those two alone. Not 猜谜 (the day's puzzle), not the scan monitor, not a
#: write -- and not 总览, which also says what a scanner has not sent home yet, from a file
#: (`data/home.json`) that `wuwa home set` writes from outside.
KEPT_ANSWERS = frozenset({
    "/api/english", "/api/find", "/api/inventory", "/api/cooking", "/api/materials",
    "/api/resonators", "/api/weapons", "/api/shops", "/api/recognized", "/api/holders",
    "/api/item",
})
#: How many answers are kept: every page in both languages, and the panels last opened.
KEEP_ANSWERS = 160

#: The lists the home sorts, searches and pages when asked (D171): path -> the list's key.
#: The pages do it in the browser; this is for whatever else asks.
LISTS = {"/api/inventory": "items", "/api/cooking": "items", "/api/materials": "groups",
         "/api/resonators": "resonators", "/api/weapons": "weapons", "/api/shops": "shops",
         "/api/recognized": "rows", "/api/english": "rows"}
LIST_QUESTIONS = ("sort", "dir", "q", "limit", "offset")


class ListQuestionError(ValueError):
    """A list question that cannot be answered: an unknown field, a bad number."""


def _whole(said: str | None, what: str) -> int | None:
    if said is None:
        return None
    if not said.isdigit():
        raise ListQuestionError(_said(f"{what} 要是 0 或更大的整数", f"{what} must be a whole number, 0 or more"))
    return int(said)


def list_query(answer: dict, key: str, asked: dict[str, str],
               english: Callable[[str], str | None]) -> dict:
    """`answer` with its list `key` searched (`q`, as the search boxes search: the name as
    written, its pinyin, initials or English), sorted (`sort`, `dir`; rows without the field
    last either way) and paged (`offset`, `limit`). `total` is how many matched (D171)."""
    from .. import search

    rows = list(answer.get(key) or [])
    typed = (asked.get("q") or "").strip()
    if typed:
        lower = typed.lower()
        squeezed = re.sub(r"[^a-z0-9]", "", lower) or lower

        def found(row: dict) -> bool:
            name = str(row.get("name") or row.get("label") or "")
            if typed in name:
                return True
            keys = row.get("find") or search.keys(name, english(name) or "")
            return lower in keys or squeezed in keys

        rows = [r for r in rows if found(r)]
    field = asked.get("sort")
    way = asked.get("dir", "asc")
    if way not in ("asc", "desc"):
        raise ListQuestionError(_said("dir 只能是 asc 或 desc", "dir must be asc or desc"))
    if field:
        if rows and not any(field in r for r in rows):
            raise ListQuestionError(_said(f"这个列表没有「{field}」", f'This list has no "{field}"'))
        have = [r for r in rows if r.get(field) is not None]
        none = [r for r in rows if r.get(field) is None]
        numeric = all(isinstance(r[field], (int, float)) and not isinstance(r[field], bool)
                      for r in have)
        have.sort(key=(lambda r: r[field]) if numeric else (lambda r: str(r[field])),
                  reverse=way == "desc")
        rows = have + none
    start = _whole(asked.get("offset"), "offset") or 0
    size = _whole(asked.get("limit"), "limit")
    total = len(rows)
    rows = rows[start:] if size is None else rows[start:start + size]
    return {**answer, key: rows, "total": total}


def _sync_routes(app: FastAPI, db_path: Path, home_key: str | None) -> None:
    """A scanner's side of the conversation with a home (D145).

    Every app answers `hello`, so a scanner pointed at the wrong one is told so.
    The rest exists only on a home (`serve --home`): what a scanner fetches is what
    the pages already show, so it is as open as they are; what a scanner *sends*
    can add scans, and needs the key.
    """
    from .. import sync

    @app.get("/api/sync/hello")
    def hello() -> dict:
        st = Store(db_path)
        try:
            # version: so a redeploy can be checked from outside (D164)
            return {"app": "wuwa-vision", "home": home_key is not None,
                    "protocol": sync.PROTOCOL, "epoch": st.sync_epoch(), "version": _version()}
        finally:
            st.close()

    if home_key is None:
        return

    def keyed(request: Request) -> None:
        if not sync.key_matches(home_key, request.headers.get("x-wuwa-key")):
            raise HTTPException(401, "上传要用主机的钥匙（data/home.key）。")

    def said(request_body: bytes) -> dict:
        try:
            body = json.loads(request_body)
        except ValueError as exc:
            raise HTTPException(400, "读不出来") from exc
        if not isinstance(body, dict):
            raise HTTPException(400, "读不出来")
        return body

    async def read(request: Request, limit: int) -> bytes:
        """The body, refused as soon as it is longer than it may be."""
        if int(request.headers.get("content-length") or 0) > limit:
            raise HTTPException(413, "太大")
        parts, size = [], 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > limit:
                raise HTTPException(413, "太大")
            parts.append(chunk)
        return b"".join(parts)

    @app.post("/api/sync/state")
    async def state(request: Request) -> dict:
        """What this home knows that the asking scanner does not."""
        theirs = said(await read(request, sync.MAX_JSON_BYTES))
        st = Store(db_path)
        try:
            return sync.state_for(st, theirs)
        except sync.SyncError as exc:
            raise HTTPException(409, str(exc)) from exc
        finally:
            st.close()

    @app.get("/api/sync/catalogue")
    def catalogue_files() -> dict:
        from ..catalogue import CATALOGUE_DIR

        return {"files": sync.catalogue_manifest(Path(CATALOGUE_DIR))}

    @app.get("/api/sync/catalogue/{rel:path}")
    def catalogue_one(rel: str) -> FileResponse:
        from ..catalogue import CATALOGUE_DIR

        path = sync.catalogue_file(Path(CATALOGUE_DIR), rel)
        if path is None:
            raise HTTPException(404, "not in the catalogue")
        return FileResponse(path, media_type="application/octet-stream")

    @app.post("/api/sync/need")
    async def need(request: Request) -> dict:
        """Of what a scanner offers, what this home lacks."""
        keyed(request)
        offered = said(await read(request, sync.MAX_JSON_BYTES))
        st = Store(db_path)
        try:
            return sync.need(st, offered)
        except sync.SyncError as exc:
            raise HTTPException(409, str(exc)) from exc
        finally:
            st.close()

    @app.post("/api/sync/scans")
    async def scans(request: Request) -> dict:
        """One upload from a scanner: finished scans, what they taught, their crops.
        Adds to what is here; replaces nothing."""
        keyed(request)
        data = await read(request, sync.MAX_BUNDLE_BYTES)
        st = Store(db_path)
        try:
            return sync.receive(st, data)
        except sync.SyncError as exc:
            raise HTTPException(409, str(exc)) from exc
        finally:
            st.close()


def _keeps_base(cat: Catalogue, name: str) -> bool:
    """Whether a base amount can be set on it: a shop sells it, or it is one of the
    密音筒, whose number is the echoes' whether a shop sells that tube or not (D161)."""
    return bool(cat.sold(name)) or exp.kind_of(cat, name) == "echo"


def _base_key(cat: Catalogue, name: str) -> str:
    """Where a thing's base amount is kept: its own name, or for any of the four
    密音筒 the one number for the echoes (D161)."""
    return shops_mod.ECHOES if exp.kind_of(cat, name) == "echo" else name


def _main_app(db_path: Path, home_key: str | None = None) -> FastAPI:
    app = FastAPI(title="WuWa Inventory Vision", docs_url="/api/docs")
    _shared_routes(app, db_path, None)
    _sync_routes(app, db_path, home_key)
    catalogue = _CatalogueCache()
    data = _DataStamp(db_path)
    answers: dict[tuple, tuple[bytes, str]] = {}

    def _kept(body: bytes, etag: str, request: Request) -> Response:
        headers = {"ETag": etag, "Cache-Control": "no-cache"}
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=headers)
        return Response(body, media_type="application/json", headers=headers)

    # The first-time walk shows sample data (D162): a page it is on asks with
    # `X-Sample: 1`, and the main app's reads and writes then go to the sample
    # database (wuwa_vision.demo), never the user's. Syncing with a home never does.
    @app.middleware("http")
    async def sample_data(request: Request, call_next):  # noqa: ANN001, ANN202
        token = _SAMPLE.set(request.headers.get("x-sample") == "1")
        english = _ENGLISH.set(request.headers.get("x-lang") == "en")
        try:
            # a list asked to be sorted, searched or paged: the whole list first (kept like
            # any answer), then the question put to it (D171)
            asked = {k: request.query_params[k] for k in LIST_QUESTIONS
                     if k in request.query_params}
            if asked and request.method == "GET" and request.url.path in LISTS:
                plain = urllib.parse.urlencode([(k, v) for k, v in request.query_params.multi_items()
                                                if k not in LIST_QUESTIONS])
                whole = await sample_data(Request({**request.scope, "query_string": plain.encode()},
                                                  request.receive), call_next)
                if whole.status_code != 200:
                    return whole
                body = getattr(whole, "body", None)
                if body is None:
                    body = b"".join([chunk async for chunk in whole.body_iterator])
                cat = catalogue.get()
                try:
                    said = list_query(json.loads(body), LISTS[request.url.path], asked, cat.english)
                except ListQuestionError as exc:
                    return JSONResponse({"detail": str(exc)}, status_code=400)
                return JSONResponse(said, headers={"Cache-Control": "no-cache"})
            # an answer that depends only on the database and the catalogue is worked out
            # once per change of either, and a browser that has it is told so (D171)
            key = None
            if (request.method == "GET" and request.url.path in KEPT_ANSWERS
                    and not _SAMPLE.get()):
                catalogue.get()
                key = (request.url.path, request.url.query, _ENGLISH.get(),
                       catalogue.version, data.get())
                if key in answers:
                    return _kept(*answers[key], request)
            response = await call_next(request)
            if key is None or response.status_code != 200                     or response.headers.get("content-type", "").split(";")[0] != "application/json":
                return response
            body = b"".join([chunk async for chunk in response.body_iterator])
            etag = '"' + hashlib.sha1(body, usedforsecurity=False).hexdigest()[:24] + '"'
            answers[key] = (body, etag)
            while len(answers) > KEEP_ANSWERS:
                answers.pop(next(iter(answers)))
            return _kept(body, etag, request)
        finally:
            _SAMPLE.reset(token)
            _ENGLISH.reset(english)
            if request.method not in ("GET", "HEAD", "OPTIONS"):
                catalogue.forget()          # a write may have been to the catalogue (D171)
                data.wrote()                # and the answers kept are of before it

    def db() -> Path:
        """The database this request is about: the user's, or the walk's sample."""
        return demo.database(catalogue.get()) if _SAMPLE.get() else db_path
    if (UI / "_next").is_dir():
        # the pages' scripts and styles (hashed names: safe to serve always)
        app.mount("/_next", StaticFiles(directory=UI / "_next"), name="next")

    @app.get("/", response_class=HTMLResponse)
    def dashboard_page() -> HTMLResponse:
        # The dashboard is what opens first (D159); 库存 has an address of its own.
        return _page("index.html")

    @app.get("/inventory", response_class=HTMLResponse)
    def inventory_page() -> HTMLResponse:
        return _page("inventory.html")

    @app.get("/shops", response_class=HTMLResponse)
    def shops_page() -> HTMLResponse:
        return _page("shops.html")

    @app.get("/cooking", response_class=HTMLResponse)
    def cooking_page() -> HTMLResponse:
        return _page("cooking.html")

    @app.get("/materials", response_class=HTMLResponse)
    def materials_page() -> HTMLResponse:
        return _page("materials.html")

    @app.get("/resonators", response_class=HTMLResponse)
    def resonators_page() -> HTMLResponse:
        return _page("resonators.html")

    @app.get("/weapons", response_class=HTMLResponse)
    def weapons_page() -> HTMLResponse:
        return _page("weapons.html")

    @app.get("/planner", response_class=HTMLResponse)
    def planner_page() -> HTMLResponse:
        return _page("planner.html")

    @app.get("/update", response_class=HTMLResponse)
    def update_page() -> HTMLResponse:
        return _page("update.html")

    @app.get("/update/{part}", response_class=HTMLResponse)
    def update_part_page(part: str) -> HTMLResponse:
        """One of 更新's parts at its own address (D164): /update/wiki … /update/data."""
        if part not in UPDATE_PARTS:
            raise HTTPException(404, "更新 has no such part")
        return _page(f"update/{part}.html")

    @app.get("/guess", response_class=HTMLResponse)
    def guess_page() -> HTMLResponse:
        return _page("guess.html")

    @app.get("/about", response_class=HTMLResponse)
    def about_page() -> HTMLResponse:
        """Whose everything is: the licence, Kuro Games' copyright, the sources (D132)."""
        return _page("about.html")

    @app.get("/help", response_class=HTMLResponse)
    def help_page() -> HTMLResponse:
        """How to start, what each page is for, what to do when something fails (D162)."""
        return _page("help.html")

    @app.get("/privacy", response_class=HTMLResponse)
    def privacy_page() -> HTMLResponse:
        """What the app keeps and what leaves the machine (D162)."""
        return _page("privacy.html")

    # The same pages in English (D164), under /en: built in English, each its own file.
    @app.get("/en", response_class=HTMLResponse)
    def english_dashboard() -> HTMLResponse:
        return _page("en.html")

    @app.get("/en/{name}", response_class=HTMLResponse)
    def english_page(name: str) -> HTMLResponse:
        if name not in PAGE_NAMES:
            raise HTTPException(404, "no such page")
        return _page(f"en/{name}.html")

    @app.get("/en/update/{part}", response_class=HTMLResponse)
    def english_update_part(part: str) -> HTMLResponse:
        if part not in UPDATE_PARTS:
            raise HTTPException(404, "更新 has no such part")
        return _page(f"en/update/{part}.html")

    @app.get("/api/privacy")
    def privacy_text() -> dict:
        """The policy as its files say it, so the page and PRIVACY.md cannot differ:
        {"en": markdown, "zh-CN": markdown}; a file that is missing is null."""
        out = {}
        for lang, name in PRIVACY.items():
            path = PROJECT / name
            out[lang] = path.read_text(encoding="utf-8") if path.is_file() else None
        return out

    @app.get("/robots.txt")
    def robots() -> Response:
        """Nothing here is for a crawler: a copy shared with a tailnet is its
        owner's inventory, not a website (TERMS.md section 2)."""
        return Response("User-agent: *\nDisallow: /\n", media_type="text/plain")

    @app.get("/favicon.svg")
    def favicon() -> FileResponse:
        """The app's own icon: drawn for it, not taken from the game (D132)."""
        icon = UI / "favicon.svg"
        if not icon.is_file():
            raise HTTPException(404, "the pages are not built")
        # asked for again each time (it is a few kilobytes): a new icon shows at once,
        # where a day's cache kept the old one in the tab
        return FileResponse(icon, media_type="image/svg+xml",
                            headers={"Cache-Control": "no-cache"})

    #: Which 漂泊者 this save has. Asked once, changed whenever (D72).
    ROVER_SETTING = "rover.gender"

    def wear_faces(rows: list[dict], faces: dict[str, str]) -> list[dict]:
        """Give a resonator with no wuwatracker avatar the portrait the scan read
        off a 武器 tile (D82): the game's own head icon, and for someone too new
        for the tracker the only real one there is."""
        for row in rows:
            if not row.get("icon") and faces.get(row.get("name") or ""):
                row["face"] = faces[row["name"]]
        return rows

    def faces_by_name(st: Store) -> dict[str, str]:
        return {name: key for key, name in st.holder_names().items()}

    def face_file(st: Store, cat, who: str | None) -> str | None:  # noqa: ANN001 -- Catalogue
        """A holder's square icon. 漂泊者 is one holder with two faces, and only
        the save's own gender is the right one (D72, D103)."""
        if not who:
            return None
        if roster.is_rover(who):
            return cat.avatar_file(f"{roster.ROVER}-{st.setting(ROVER_SETTING) or '男'}-衍射")
        return cat.avatar_file(who)

    def hidden(st: Store) -> frozenset[str]:
        """The 漂泊者 forms this save cannot have -- hidden, and never counted."""
        return roster.other_gender_rovers(catalogue.get(), st.setting(ROVER_SETTING))

    def dropped_by(cat: Catalogue, name: str) -> dict:
        """The boss behind a boss or weekly drop, for a picker to show beside it (D124)."""
        role, drop = role_of(cat, name)
        icon = cat.bosses.get(drop or "")
        return {"role": role, "drop": drop, "drop_icon": icon} if drop else {}

    def progress_of(st: Store) -> dict[str, dict]:
        """What the user saved, with the 漂泊者's level and ascension on every one
        of its forms (D118). For reading; a save still writes one form's row."""
        return roster.shared_rover(catalogue.get(), st.progress(), hidden(st))

    @app.get("/api/rover")
    def rover_gender() -> dict:
        st = Store(db())
        try:
            gender = st.setting(ROVER_SETTING)
        finally:
            st.close()
        cat = catalogue.get()
        return {"gender": gender, "asked": gender in roster.GENDERS,
                "genders": list(roster.GENDERS),
                # the two faces, so the question can be asked with pictures (D81)
                "icons": {g: cat.avatar_file(f"{roster.ROVER}-{g}-衍射")
                          for g in roster.GENDERS}}

    @app.post("/api/rover")
    def set_rover_gender(body: RoverGender) -> dict:
        st = Store(db())
        try:
            st.set_setting(ROVER_SETTING, body.gender)
        finally:
            st.close()
        return {"gender": body.gender}

    def done_tabs(st: Store) -> set[str]:
        return {t["tab"] for t in tab_summary(st) if t["complete"]}

    def cooking_needs(st: Store, cat: Catalogue, inventory: list) -> dict[str, int]:
        """What dishes still below their target would take of each ingredient (D58)."""
        from ..cooking import ingredient_needs

        return ingredient_needs(dishes_of(st, cat, inventory))

    def dishes_of(st: Store, cat: Catalogue, inventory: list) -> list:
        """Every dish and potion, knowing who is on the account to cook (D126)."""
        complete = any(t["tab"] == CRAFT_TAB and t["complete"] for t in tab_summary(st))
        cooks = roster.on_account(cat, progress_of(st), read_pulls(st), hidden(st))
        return build_cooking(st, cat, inventory, tab_complete=complete, cooks=cooks)

    @app.get("/api/resonators")
    def resonator_list() -> dict:
        st = Store(db())
        try:
            cat = catalogue.get()
            rows = wear_faces(
                roster.resonators(cat, build_inventory(st, cat), done_tabs(st), progress_of(st),
                                  read_pulls(st), skip=hidden(st)),
                faces_by_name(st),
            )
            gender = st.setting(ROVER_SETTING)
        finally:
            st.close()
        return {"resonators": rows, "monitor_port": LIVE_PORT, "rover": gender}

    @app.get("/api/resonator")
    def resonator_detail(name: str) -> dict:
        """One resonator: profile, 立绘, 特殊料理, one full build against stock (D46)."""
        st = Store(db())
        try:
            cat = catalogue.get()
            found = roster.resonator(cat, build_inventory(st, cat), name, done_tabs(st),
                                     progress_of(st).get(name), read_pulls(st))
            wallet = st.wallet()
            if found is not None:
                with_scan(st, found["weapons"])  # the bag's counts, not the pulls' (D103)
            carried = weapons_mod.held(st)
            # A 漂泊者 form is carrying whatever "漂泊者" was named as holding.
            copy = carried.get(name) or (
                carried.get(roster.ROVER) if roster.is_rover(name) else None
            )
            holding = copy.name if copy else None
            # The copy itself, for the top of the panel: which one, at what level.
            holding_copy = {
                "name": copy.name, "level": copy.level, "rank": copy.rank,
                "rarity": (cat.entry(copy.name) or {}).get("rarity"),
                "icon_file": cat.icon_file(copy.name),
            } if copy else None
        finally:
            st.close()
        if found is None:
            raise HTTPException(404, "unknown resonator")
        return {**found, "english": cat.english(name), "wallet": wallet, "holding": holding,
                "holding_copy": holding_copy}

    @app.post("/api/resonator/progress")
    def set_progress(body: Progress) -> dict:
        """Save (or forget) where a resonator stands: the pages then count only what
        is left, and the planner starts from it (D50)."""
        cat = catalogue.get()
        if planner.limits(cat, "resonator", body.name) is None:
            raise HTTPException(404, "unknown resonator")
        st = Store(db())
        try:
            if body.state is None:
                st.clear_progress(body.name)
                return {"name": body.name, "state": None}
            state = planner.clamp(cat, "resonator", body.name, body.state)
            st.set_progress(body.name, body.owned, state)
            return {"name": body.name, "owned": body.owned, "state": state}
        finally:
            st.close()

    @app.post("/api/resonator/progress/bulk")
    def set_progress_bulk(body: BulkProgress) -> dict:
        """One request for what the page used to do one resonator at a time, each after
        fetching its whole page for its caps (D194). 已拥有 keeps what is saved."""
        cat = catalogue.get()
        known = [n for n in dict.fromkeys(body.names)
                 if planner.limits(cat, "resonator", n) is not None]
        st = Store(db())
        try:
            saved = st.progress()
            for name in known:
                if body.how == "clear":
                    st.clear_progress(name)
                elif body.how == "max":
                    st.set_progress(name, True, planner.full(cat, "resonator", name, True))
                else:
                    mine = (saved.get(name) or {}).get("state")
                    state = (planner.clamp(cat, "resonator", name, mine) if mine
                             else planner.full(cat, "resonator", name, False))
                    st.set_progress(name, True, state)
            return {"done": len(known),
                    "unknown": [n for n in dict.fromkeys(body.names) if n not in known]}
        finally:
            st.close()

    @app.post("/api/resonator/chain")
    def set_chain(body: Chain) -> dict:
        """A pull export cannot see a copy that came free or in a top-up pack, so
        the 共鸣链 can be set by hand and then outranks the pulls (D69)."""
        if body.name not in catalogue.get().builds.get("resonators", {}):
            raise HTTPException(404, "unknown resonator")
        st = Store(db())
        try:
            st.set_chain(body.name, body.chain)
            return {"name": body.name, "chain": body.chain}
        finally:
            st.close()

    @app.post("/api/resonator/owned")
    def set_owned(body: Owned) -> dict:
        """Someone no pull shows -- given away, bought, in a pack -- is on the account
        because the user says so (D116). Kept through 清空扫描数据, like the chain."""
        if body.name not in catalogue.get().builds.get("resonators", {}):
            raise HTTPException(404, "unknown resonator")
        st = Store(db())
        try:
            st.set_owned(body.name, body.owned)
            return {"name": body.name, "owned": body.owned}
        finally:
            st.close()

    def why(st: Store, cat: Catalogue, name: str, inventory: list, done: set[str],
            away: frozenset[str], progress: dict[str, dict]) -> dict:
        """Where this material's target comes from, with pictures for the panel (D122)."""
        dishes = ingredient_sources(dishes_of(st, cat, inventory)).get(name, [])
        out = reasons(cat, name, done, away, st.material_targets(),
                      roster.needed_by(cat, progress, read_pulls(st), away), dishes,
                      st.base_amounts())
        people = cat.builds.get("resonators", {})
        faces = faces_by_name(st)
        for part in out["builds"]:
            if part["kind"] == "resonator":
                part["who"] = roster.avatar(cat, part["name"], people[part["name"]], faces)
            else:
                part["icon_file"] = cat.icon_file(part["name"])
                part["rarity"] = (cat.builds["weapons"].get(part["name"]) or {}).get("rarity") or 0
        return out

    def read_pulls(st: Store) -> dict | None:
        from .. import pulls as pulls_mod

        return pulls_mod.resolve(st.pulls(), catalogue.get())

    @app.get("/api/pulls")
    def pulls_state() -> dict:
        st = Store(db())
        try:
            found = read_pulls(st)
        finally:
            st.close()
        if not found:
            return {"imported": False}
        from .. import pulls as pulls_mod
        from ..catalogue import read_pull_names

        cat = catalogue.get()
        # A name this machine gave that the app now ships the same (D144) is no longer
        # this machine's to take back: taking it back would change nothing.
        shipped = {gid: entry.get("name") for entries in read_pull_names().values()
                   for gid, entry in entries.items()}
        mine = {gid: name for gid, name in cat.overrides["gids"].items()
                if shipped.get(str(gid)) != name}
        return {"imported": True, "date": found["date"], "imported_at": found["imported_at"],
                "pulls": found["pulls"], "resonators": len(found["resonators"]),
                "weapons": len(found["weapons"]),
                "unknown": [pulls_mod.describe(u) for u in found["unknown"]],
                # what this machine's user has named by hand, to see and to take back (D135)
                "named": [{"gid": gid, "name": name, "kind": pulls_mod.kind_of(gid),
                           "english": cat.overrides["pull_english"].get(gid, "")}
                          for gid, name in sorted(mine.items())]}

    @app.post("/api/pulls/name")
    def name_pull(body: PullName) -> dict:
        """Say which weapon or resonator a pull's id is (D135). Kept in
        overrides.json with the English name the export gave it, so the same pull
        is placed by id or by name from then on. An empty name takes it back --
        for the next import: one already counted stays counted, because an import
        keeps counts, not the pulls they came from."""
        from .. import pulls as pulls_mod
        from ..catalogue import read_overrides, write_overrides

        gid = body.gid.strip()
        if not gid.isdigit() or not 4 <= len(gid) <= 12:
            raise HTTPException(400, _said("不是游戏编号", "Not a game id"))
        cat = catalogue.get()
        name = body.name.strip()
        if name:
            known = (set(cat.builds.get("weapons", {})) | {
                n for n in cat.names() if (cat.entry(n) or {}).get("tab") == "武器"}
                if pulls_mod.kind_of(gid) == "weapon" else set(cat.builds.get("resonators", {})))
            if name not in known:
                raise HTTPException(400, _said(f"图鉴里没有「{name}」",
                                               f"The catalogue has no \"{name}\""))
        st = Store(db())
        try:
            stored = st.pulls() or {}
        finally:
            st.close()
        english = next((u.get("name") or "" for u in stored.get("unknown", [])
                        if str(u.get("gid")) == gid), "")
        data = read_overrides()
        if name:
            data["gids"][gid] = name
            if english:
                data["pull_english"][gid] = english
        else:
            data["gids"].pop(gid, None)
            data["pull_english"].pop(gid, None)
        write_overrides(data)
        catalogue.forget()             # read back at once, not in CATALOGUE_LOOK
        return pulls_state()

    @app.post("/api/pulls")
    async def import_pulls(request: Request) -> dict:
        """A wuwatracker pull export, uploaded by the user (D53): only the counts
        are kept, replacing the previous import."""
        from .. import pulls as pulls_mod

        body = await request.body()
        if len(body) > MAX_PULLS_BYTES:
            raise HTTPException(413, "file too large")
        try:
            export = json.loads(body)
            data = pulls_mod.parse(export, catalogue.get())
        except (ValueError, TypeError) as exc:
            raise HTTPException(400, _said(f"不是 wuwatracker 的抽卡记录：{exc}",
                                           f"Not a wuwatracker pull history: {exc}")) from exc
        st = Store(db())
        try:
            st.set_pulls(data)
        finally:
            st.close()
        return pulls_state()

    def with_scan(st: Store, rows: list[dict]) -> dict:
        """Fold in what the 武器 tab scan saw: levels, and who is carrying what (D62)."""
        mine = weapons_mod.by_weapon(st)
        cat = catalogue.get()
        counts, complete = weapons_mod.owned_counts(st, (read_pulls(st) or {}).get("weapons"))
        for weapon in rows:
            found = mine.get(weapon["name"], [])
            weapon["scanned"] = [c.as_dict() for c in found]
            weapon.update(weapons_mod.summary(found))
            # One number for "how many do I own", the same on every page (D103).
            weapon["owned_count"] = counts.get(weapon["name"], 0)
            weapon["bag_complete"] = complete
            weapon["holder_icons"] = [face_file(st, cat, c.holder) for c in found if c.holder]
        return {"scan": weapons_mod.latest_scan(st),
                "faces": weapons_mod.faces(st, catalogue.get()),
                "unknown": weapons_mod.unknown(st)}

    @app.get("/api/weapons")
    def weapon_list() -> dict:
        st = Store(db())
        try:
            pulls = read_pulls(st)
            rows = roster.weapons(catalogue.get(), pulls)
            scan = with_scan(st, rows)
        finally:
            st.close()
        return {"weapons": rows, "pulls_at": (pulls or {}).get("date"),
                "monitor_port": LIVE_PORT, **scan}

    @app.get("/api/recognized")
    def recognized() -> dict:
        """What the scanners have learned (D166): every picture saved from the game under a
        name, by name, beside the catalogue's own picture; the ones the catalogue is sure are
        another item flagged, and listed first."""
        from ..recognize import review

        cat = catalogue.get()
        weapons = set((cat.builds.get("weapons") or {}).keys())
        st = Store(db())
        try:
            crops = review.learned(st)
        finally:
            st.close()
        by_name: dict[str, list] = {}
        for crop in crops:
            by_name.setdefault(crop.name, []).append(crop)
        rows = []
        for name, mine in by_name.items():
            # flagged first, then the ones a person said are right (D167), so a decision just
            # made stays in sight; then the rest, oldest first
            mine.sort(key=lambda c: (c.doubt is None, not c.confirmed, -c.margin, c.created_at))
            entry = cat.entry(name) or {}
            icon = cat.icon_file(name)
            rows.append({
                "name": name,
                "kind": "武器" if name in weapons else entry.get("tab") or mine[0].tab or "物品",
                "rarity": entry.get("rarity") or mine[0].rarity or 0,
                "icon": f"/api/reference/{icon}" if icon else None,
                "count": len(mine),
                "doubtful": sum(c.doubt is not None for c in mine),
                "crops": [{"hash": c.hash, "created_at": c.created_at,
                           "doubt": {"name": c.doubt, "margin": round(c.margin, 3)}
                           if c.doubt else None, "confirmed": c.confirmed} for c in mine],
            })
        rows.sort(key=lambda r: (-r["doubtful"], r["name"]))
        return {"rows": rows, "counts": {"names": len(rows), "crops": len(crops),
                                         "doubtful": sum(r["doubtful"] for r in rows)}}

    def _crop_fix(fix: CropName, name: str | None) -> dict:
        st = Store(db())
        try:
            if not st.learned_crop(fix.hash):
                raise HTTPException(404, _said("没有这张图", "No such picture"))
            return {"hash": fix.hash, "name": name, **st.rename_crop(fix.hash, name)}
        finally:
            st.close()

    @app.post("/api/recognized/name")
    def recognized_name(fix: CropName) -> dict:
        """Give a learned picture another name (D166): it, its same pictures, and the scans
        that saw them. Only a name the catalogue has."""
        cat = catalogue.get()
        name = (fix.name or "").strip()
        if name not in cat.names() and name not in (cat.builds.get("weapons") or {}):
            raise HTTPException(400, _said(f"图鉴里没有「{name}」",
                                           f"The catalogue has no \"{name}\""))
        return _crop_fix(fix, name)

    @app.post("/api/recognized/forget")
    def recognized_forget(fix: CropName) -> dict:
        """Take a learned picture's name away (D166): its copies are then to be named again."""
        return _crop_fix(fix, None)

    @app.post("/api/recognized/confirm")
    def recognized_confirm(fix: CropName) -> dict:
        """Say a flagged picture's name is right (D167): it and its same pictures under that
        name are not flagged again, until they are given another name."""
        st = Store(db())
        try:
            done = st.confirm_crop(fix.hash)
        finally:
            st.close()
        if done is None:
            raise HTTPException(404, _said("没有这张图", "No such picture"))
        return {"hash": fix.hash, **done}

    @app.post("/api/item-name")
    def name_item(fix: ItemName) -> dict:
        """Name an unnamed tile (D65): the scan's rows and its crops in one go."""
        cat = catalogue.get()
        name = fix.name.strip()
        if name not in cat.names() and name not in cat.builds.get("weapons", {}):
            raise HTTPException(404, "unknown item")
        st = Store(db())
        try:
            return {"key": fix.key, "name": name,
                    "rows": st.name_item(fix.scan_id, fix.key, name)}
        finally:
            st.close()

    @app.post("/api/item/forget")
    def forget_item(gone: ItemForget) -> dict:
        """Delete a tile that is not an item: its sightings and its crops (D66)."""
        st = Store(db())
        try:
            return {"key": gone.key, "rows": st.forget_item(gone.scan_id, gone.key)}
        finally:
            st.close()

    @app.get("/api/holders")
    def holder_faces() -> dict:
        """The portraits the 武器 tiles wore, and everyone they could be (D61).

        The reference avatars are close enough to spot a portrait but not to name
        one, so the page shows the face and the user picks -- once per face.
        """
        cat = catalogue.get()
        st = Store(db())
        try:
            found = weapons_mod.faces(st, cat)
            owned = set(st.progress())
            away = hidden(st)
            faces = faces_by_name(st)
        finally:
            st.close()
        people = cat.builds.get("resonators", {})
        rows = wear_faces([
            roster.avatar(cat, n, b) | {"owned": n in owned}
            for n, b in people.items() if not roster.is_rover(n)
        ], faces)
        # The 漂泊者 forms are one character with four elements, and only one of
        # them can be carrying a weapon at any time -- so the picker offers one
        # 漂泊者, not eight (D72).
        rover = next((n for n in people if roster.is_rover(n) and n not in away), None)
        if rover is not None:
            rows.append(
                roster.avatar(cat, rover, people[rover])
                | {"name": roster.ROVER, "owned": True, "element": None}
            )
        return {
            "faces": found,
            "resonators": sorted(rows, key=lambda r: (not r["owned"], -r["rarity"], r["name"])),
        }

    @app.post("/api/holder")
    def name_holder(fix: HolderName) -> dict:
        """Name a portrait -- the only way a face is ever named (D61)."""
        st = Store(db())
        try:
            known = catalogue.get().builds.get("resonators", {})
            # 漂泊者 is offered as one name, not eight forms (D72).
            if fix.name and fix.name != roster.ROVER and fix.name not in known:
                raise HTTPException(404, "unknown resonator")
            st.set_holder_name(fix.key, fix.name or None)
            return {"key": fix.key, "name": fix.name or None}
        finally:
            st.close()

    @app.get("/api/art/{filename}")
    def resonator_art(filename: str) -> FileResponse:
        """A resonator's card or 立绘 (fetch_builds.py). The name is checked against a
        strict pattern, so it cannot walk out of the art directory."""
        from ..catalogue import CATALOGUE_DIR

        path = CATALOGUE_DIR / "resonators" / filename
        if not _ART_FILE.match(filename) or not path.exists():
            raise HTTPException(404, "unknown art")
        return FileResponse(path, media_type="image/webp",
                            headers={"Cache-Control": "max-age=86400"})

    # ------------------------------------------------------------ planner (D47)
    @app.get("/api/plans")
    def plans() -> dict:
        """Every plan with its cost, and all of them against the stock."""
        st = Store(db())
        try:
            cat = catalogue.get()
            mine = progress_of(st)
            plans = [{**p, "current": mine[p["name"]]["state"]}
                     if p["kind"] == "resonator" and p["name"] in mine else p
                     for p in st.plans()]
            out = planner.view(cat, build_inventory(st, cat), plans, done_tabs(st))
            wallet = st.wallet()
        finally:
            st.close()
        return {**out, "wallet": wallet, "monitor_port": LIVE_PORT}

    @app.get("/api/dashboard")
    def dashboard() -> dict:
        """The dashboard's cards (D159): what can be paid for, what is short, and
        whether the numbers hold. Every number is one another page shows."""
        from .. import sync

        st = Store(db())
        try:
            cat = catalogue.get()
            inventory = build_inventory(st, cat)
            owned = {i.name: i.count or 0 for i in inventory if i.name}
            mine = progress_of(st)
            plans = [{**p, "current": mine[p["name"]]["state"]}
                     if p["kind"] == "resonator" and p["name"] in mine else p
                     for p in st.plans()]
            # a scanner with a home (D145): what has not been handed over yet
            home = sync.read_home(Path(db_path).parent)
            unsent = ({"count": len(sync.unsent_scans(st)), "home": home["url"]}
                      if home else None)
            return {
                "pay": dashboard_mod.pay(cat, owned, st.wallet(), st.echo_base()),
                "short": dashboard_mod.short(
                    shops_mod.to_buy(cat, owned, st.base_amounts()),
                    [d.as_dict() for d in dishes_of(st, cat, inventory)],
                    planner.view(cat, inventory, plans, done_tabs(st)),
                    [g.as_dict() for g in material_groups(st, cat, inventory)]),
                "trust": dashboard_mod.trust(tab_summary(st), inventory, unsent),
                # whether the shop table was ever fetched: "nothing to buy" means
                # something else without it
                "has_shops": bool(cat.shops),
                "scanned": bool(inventory),
                "monitor_port": LIVE_PORT,
            }
        finally:
            st.close()

    @app.post("/api/plans")
    def add_plan(new: PlanNew) -> dict:
        if new.kind not in ("resonator", "weapon"):
            raise HTTPException(400, "kind must be resonator or weapon")
        cat = catalogue.get()
        if planner.limits(cat, new.kind, new.name) is None:
            raise HTTPException(404, f"unknown {new.kind}")
        st = Store(db())
        try:
            saved = progress_of(st).get(new.name) if new.kind == "resonator" else None
            state = {"current": saved["state"] if saved
                     else planner.full(cat, new.kind, new.name, top=False),
                     "target": planner.full(cat, new.kind, new.name, top=True)}
            return {"id": st.add_plan(new.kind, new.name, state)}
        finally:
            st.close()

    @app.post("/api/plans/{plan_id}")
    def set_plan(plan_id: int, body: PlanState) -> dict:
        st = Store(db())
        try:
            found = next((p for p in st.plans() if p["id"] == plan_id), None)
            if found is None:
                raise HTTPException(404, "unknown plan")
            cat = catalogue.get()
            state = {k: planner.clamp(cat, found["kind"], found["name"], v)
                     for k, v in (("current", body.current), ("target", body.target))}
            st.set_plan_state(plan_id, state)
            if found["kind"] == "resonator":  # one truth for where a resonator stands
                owned = st.progress().get(found["name"], {}).get("owned", True)
                st.set_progress(found["name"], owned, state["current"])
            return state
        finally:
            st.close()

    @app.post("/api/plans/{plan_id}/remove")
    def remove_plan(plan_id: int) -> dict:
        st = Store(db())
        try:
            st.remove_plan(plan_id)
        finally:
            st.close()
        return {"removed": plan_id}

    @app.get("/api/boss/{filename}")
    def boss_icon(filename: str) -> FileResponse:
        """A boss portrait (tools/fetch_bosses.py): "<entry id>.webp" only."""
        from ..catalogue import CATALOGUE_DIR

        path = CATALOGUE_DIR / "bosses" / filename
        if not _ART_FILE.match(filename) or not path.exists():
            raise HTTPException(404, "unknown boss")
        return FileResponse(path, media_type="image/webp",
                            headers={"Cache-Control": "max-age=86400"})

    @app.get("/api/shop/{filename}")
    def shop_icon(filename: str) -> FileResponse:
        """A shop's picture (tools/fetch_shops.py, D160): "<shop id>.webp" only;
        or the marker of a kind of shop the app ships (D161): "shop-grocer.webp"."""
        from ..catalogue import CATALOGUE_DIR

        if filename in SHOP_MARKERS:
            return FileResponse(ICONS / filename, media_type="image/webp",
                                headers={"Cache-Control": "max-age=86400"})
        path = CATALOGUE_DIR / "shops" / filename
        if not _ART_FILE.match(filename) or not path.exists():
            raise HTTPException(404, "unknown shop")
        return FileResponse(path, media_type="image/webp",
                            headers={"Cache-Control": "max-age=86400"})

    @app.get("/api/ui-icon/{filename}")
    def ui_icon(filename: str) -> FileResponse:
        """A picture of the app's own (D162): one of 更新's parts, nothing else."""
        if filename not in PART_ICONS:
            raise HTTPException(404, "unknown icon")
        return FileResponse(ICONS / filename, media_type="image/png",
                            headers={"Cache-Control": "max-age=86400"})

    @app.get("/api/avatar/{filename}")
    def avatar_icon(filename: str) -> FileResponse:
        """A resonator icon or an element / weapon-type icon (D49), strict names only."""
        from ..catalogue import CATALOGUE_DIR, GAME_ICONS, WEAPON_TYPE_ICONS

        if filename in WEAPON_TYPE_ICONS.values():  # the app's own drawings (D133)
            return FileResponse(ICONS / filename, media_type="image/svg+xml",
                                headers={"Cache-Control": "no-cache"})
        if not _AVATAR_FILE.match(filename):
            raise HTTPException(404, "unknown icon")
        path = CATALOGUE_DIR / "avatars" / filename
        if not path.exists():
            # the slot for a user's own weapon-type icons; the app puts nothing there (D140)
            path = GAME_ICONS / filename
            drawn = {name.rsplit(".", 1)[0] for name in WEAPON_TYPE_ICONS.values()}
            if filename.rsplit(".", 1)[0] not in drawn or not path.exists():
                raise HTTPException(404, "unknown icon")
        media = "image/png" if filename.endswith(".png") else "image/webp"
        return FileResponse(path, media_type=media, headers={"Cache-Control": "max-age=86400"})

    # ---------------------------------------------------------- 猜谜 (D147)

    # A guess reads the round and writes it back with one more name in it. Two at
    # once (a quick second Enter, a second machine) would each write over the
    # other's, so whatever changes a round takes its turn.
    guess_turn = threading.Lock()

    def guess_level(st: Store, mode: str) -> str:
        """The level the next round of `mode` is played at. A free round takes the
        one last chosen; a day's round takes the one chosen that day and otherwise
        starts at 普通 -- yesterday's 噩梦 is not today's, since a guess fixes it."""
        day, _, level = (st.setting(f"guess.level.{mode}") or "").rpartition("|")
        if mode == "daily" and day != guess.today().isoformat():
            return guess.DEFAULT_LEVEL
        return level if level in guess.LEVELS else guess.DEFAULT_LEVEL

    def set_guess_level(st: Store, mode: str, level: str) -> None:
        day = guess.today().isoformat() if mode == "daily" else ""
        st.set_setting(f"guess.level.{mode}", f"{day}|{level}")

    def guess_state(st: Store) -> dict:
        cat = catalogue.get()
        gender = st.setting(ROVER_SETTING)
        day = guess.today()
        before = guess.daily_answer(cat, day - timedelta(days=1), gender)
        out = {
            "day": day.isoformat(),
            "levels": [{"name": n, "tries": t} for n, t in guess.LEVELS.items()],
            "people": guess.people(cat, gender),
            "record": guess.record(st.guess_rounds(), day),
            "yesterday": guess.person(cat, before) if before else None,
            "monitor_port": LIVE_PORT,
        }
        for mode in guess.MODES:
            out[mode] = guess.view(cat, st.guess_round(mode, day.isoformat()),
                                   guess_level(st, mode))
        return out

    @app.get("/api/guess")
    def guess_get() -> dict:
        st = Store(db())
        try:
            return guess_state(st)
        finally:
            st.close()

    @app.post("/api/guess/level")
    def guess_set_level(body: GuessLevel) -> dict:
        """The level is the player's to choose until the first guess of a round."""
        if body.level not in guess.LEVELS:
            raise HTTPException(422, "unknown level")
        st = Store(db())
        try:
            guess_turn.acquire()
            round_ = st.guess_round(body.mode, guess.today().isoformat())
            if round_ and round_["guesses"] and (body.mode == "daily" or not round_["result"]):
                raise HTTPException(409, "the level is set once a round has a guess in it")
            set_guess_level(st, body.mode, body.level)
            if round_ and not round_["guesses"]:
                st.set_guess_level(round_["id"], body.level)
            return guess_state(st)
        finally:
            guess_turn.release()
            st.close()

    @app.post("/api/guess/try")
    def guess_try(body: GuessTry) -> dict:
        st = Store(db())
        try:
            guess_turn.acquire()
            cat = catalogue.get()
            gender = st.setting(ROVER_SETTING)
            day = guess.today()
            if body.name not in guess.pool(cat, gender):
                raise HTTPException(404, "nobody by that name can be guessed")
            round_ = st.guess_round(body.mode, day.isoformat())
            if round_ is None or (body.mode == "free" and round_["result"]):
                daily = guess.daily_answer(cat, day, gender)
                answer = daily if body.mode == "daily" else guess.free_answer(
                    cat, gender, {daily or "", (round_ or {}).get("answer") or ""})
                round_ = st.start_guess_round(
                    body.mode, day.isoformat() if body.mode == "daily" else None,
                    guess_level(st, body.mode), answer)
            if round_["result"]:
                raise HTTPException(409, "this round is over")
            if body.name in round_["guesses"]:
                raise HTTPException(409, "already guessed")
            result = guess.judge(cat, round_, body.name)
            st.save_guess_round(round_["id"], [*round_["guesses"], body.name],
                                round_["notes"], result)
            return guess_state(st)
        finally:
            guess_turn.release()
            st.close()

    @app.post("/api/guess/note")
    def guess_note(body: GuessNote) -> dict:
        """A mark the player puts on a cell of a 噩梦 row. Kept, never checked."""
        if body.column not in guess.columns(guess.BLIND) or body.mark not in (None, *guess.NOTES):
            raise HTTPException(422, "unknown column or mark")
        st = Store(db())
        try:
            guess_turn.acquire()
            round_ = st.guess_round(body.mode, guess.today().isoformat())
            if not round_ or round_["level"] != guess.BLIND or body.row >= len(round_["guesses"]):
                raise HTTPException(409, "there is no such cell to mark")
            notes = dict(round_["notes"])
            key = f"{body.row}:{body.column}"
            if body.mark:
                notes[key] = body.mark
            else:
                notes.pop(key, None)
            st.save_guess_round(round_["id"], round_["guesses"], notes, round_["result"])
            return guess_state(st)
        finally:
            guess_turn.release()
            st.close()

    @app.post("/api/guess/new")
    def guess_new(body: GuessNew) -> dict:
        """Another free round. One left unfinished is dropped: it was not played."""
        st = Store(db())
        try:
            guess_turn.acquire()
            cat = catalogue.get()
            gender = st.setting(ROVER_SETTING)
            last = st.guess_round(body.mode)
            if last and not last["result"]:
                st.drop_guess_round(last["id"])
            daily = guess.daily_answer(cat, guess.today(), gender)
            answer = guess.free_answer(cat, gender, {daily or "", (last or {}).get("answer") or ""})
            if answer is None:
                raise HTTPException(409, "there is nobody to guess")
            st.start_guess_round(body.mode, None, guess_level(st, body.mode), answer)
            return guess_state(st)
        finally:
            guess_turn.release()
            st.close()

    # --------------------------------------------------- catalogue update (D46)
    job = UpdateJob()

    @app.get("/api/update")
    def update_state() -> dict:
        return job.as_dict()

    @app.post("/api/update/start")
    def update_start(req: UpdateStart) -> dict:
        """Run the catalogue setup tools: the one user-clicked outbound action."""
        job.seed = req.seed
        if not job.start():
            raise HTTPException(409, "an update is already running")
        return job.as_dict()

    @app.get("/api/overrides")
    def overrides() -> dict:
        cat = catalogue.get()
        # Resonators the catalogue knows of but has no ascension table for: the
        # ones this page exists to fill in (D74).
        blank = sorted(
            n for n, b in cat.builds["resonators"].items() if not (b.get("materials") or {})
        )
        st = Store(db())
        try:
            away = hidden(st)
        finally:
            st.close()
        # Everything that can be edited, as pictures: the 更新 page picks from
        # these rather than asking the user to type a name they have to know (D79).
        rovers = rover_only(cat)
        items = [
            {"name": n, "rarity": (e or {}).get("rarity") or 0, "tab": (e or {}).get("tab"),
             "icon_file": cat.icon_file(n), "slot": slot_of(cat, n), **dropped_by(cat, n),
             # the 漂泊者's own: a picker for anyone else's build leaves it out (D143)
             **({"rover": True} if n in rovers else {})}
            for n in sorted(cat.names()) if (e := cat.entry(n)) and e.get("tab") != WEAPON_TAB
        ]
        from .. import search

        weapons = [
            {"name": n, "rarity": b.get("rarity") or 0, "type": b.get("type"),
             "find": search.keys(n, cat.english(n) or ""),
             "icon_file": cat.icon_file(n), "materials": b.get("materials") or {}}
            for n, b in sorted(cat.builds["weapons"].items())
        ]
        people = [
            {"name": n, "rarity": b.get("rarity") or 0, "element": b.get("element"),
             "find": search.keys(n, cat.english(n) or b.get("english") or ""),
             "weapon": b.get("weapon"), "icon": cat.avatar_file(n),
             "card": b.get("card"), "materials": b.get("materials") or {},
             "blank": not (b.get("materials") or {})}
            for n, b in sorted(cat.builds["resonators"].items()) if n not in away
        ]
        return {**read_overrides(), "names": sorted(cat.names()),
                "weapon_types": sorted({w.get("type") for w in cat.builds["weapons"].values()
                                        if w.get("type")}),
                "elements": sorted({b.get("element") for b in cat.builds["resonators"].values()
                                    if b.get("element")}),
                "resonator_names": sorted(cat.builds["resonators"]),
                "without_materials": blank,
                # for the build forms (D115): which materials go together, and what
                # a build usually takes of each box
                "all_families": families(cat),
                "typical": {"resonator": typical(cat, "resonators"),
                            "weapon": typical(cat, "weapons")},
                "catalogue": {"items": items, "weapons": weapons, "resonators": people}}

    def edit(change) -> dict:  # noqa: ANN001 -- change(overrides) mutates in place
        data = read_overrides()
        change(data)
        write_overrides(data)
        catalogue.forget()             # read back at once, not in CATALOGUE_LOOK
        return read_overrides()

    @app.post("/api/overrides/item")
    def override_item(item: ItemOverride) -> dict:
        fields = {k: v for k, v in item.model_dump().items() if k != "name" and v != ""}
        return edit(lambda d: d["items"].__setitem__(item.name.strip(), fields))

    @app.post("/api/overrides/family")
    def override_family(family: FamilyOverride) -> dict:
        names = [n.strip() for n in family.names if n.strip()]
        if len(set(names)) != len(names) or len(names) < 2:
            raise HTTPException(400, "a family needs two or more different materials")

        def change(d: dict) -> None:
            d["families"] = [f for f in d["families"] if not set(f) & set(names)] + [names]
        return edit(change)

    @app.post("/api/overrides/weapon")
    def override_weapon(w: WeaponOverride) -> dict:
        body = {"type": w.type, "rarity": w.rarity,
                "materials": {k.strip(): v for k, v in w.materials.items() if k.strip() and v > 0}}
        return edit(lambda d: d["weapons"].__setitem__(w.name.strip(), body))

    @app.post("/api/overrides/resonator")
    def override_resonator(r: ResonatorOverride) -> dict:
        """Fill in a resonator the wiki has no build for yet (D74).

        The materials must already exist -- add a brand-new one in the 材料 box
        first, or wait for the catalogue update that brings it -- so a typo
        cannot invent a material that nothing will ever match.
        """
        cat = catalogue.get()
        materials = {k.strip(): v for k, v in r.materials.items() if k.strip() and v > 0}
        unknown = [n for n in materials if n not in cat.names() and n not in CURRENCY]
        if unknown:
            raise HTTPException(400, _said(
                f"图鉴里没有这些材料：{'、'.join(unknown)}",
                f"The catalogue has none of these materials: {', '.join(unknown)}"))
        body: dict = {"rarity": r.rarity, "materials": materials}
        if r.element.strip():
            body["element"] = r.element.strip()
        if r.weapon.strip():
            body["weapon"] = r.weapon.strip()
        return edit(lambda d: d["resonators"].__setitem__(r.name.strip(), body))

    @app.post("/api/overrides/signature")
    def override_signature(fix: SignatureFix) -> dict:
        def change(d: dict) -> None:
            if fix.weapon is None:
                d["signatures"].pop(fix.resonator, None)
            else:
                d["signatures"][fix.resonator] = fix.weapon.strip()
        return edit(change)

    @app.post("/api/overrides/remove")
    def override_remove(r: Removal) -> dict:
        if r.kind not in ("items", "weapons", "families", "resonators"):
            raise HTTPException(400, "kind must be items, weapons, families or resonators")

        def change(d: dict) -> None:
            if r.kind == "families":
                d["families"] = [f for f in d["families"] if "|".join(f) != r.key]
            else:
                d[r.kind].pop(r.key, None)
        return edit(change)

    @app.get("/api/cooking")
    def cooking() -> dict:
        """Every dish and potion against its stock target (D45 decisions 6-8)."""
        st = Store(db())
        try:
            cat = catalogue.get()
            items = dishes_of(st, cat, build_inventory(st, cat))
            return {
                "defaults": default_targets(st),
                "items": [c.as_dict() for c in items],
                "monitor_port": LIVE_PORT,
            }
        finally:
            st.close()

    def material_groups(st: Store, cat: Catalogue, inventory: list) -> list:
        """材料's groups, as that page has them; 总览 shows their short tiers (D181)."""
        done = {t["tab"] for t in tab_summary(st) if t["complete"]}
        away = hidden(st)
        progress = progress_of(st)
        return build_materials(cat, inventory, complete_tabs=done,
                               done=roster.finished(cat, progress),
                               extra=cooking_needs(st, cat, inventory), skip=away,
                               wanted=st.material_targets(),
                               still=roster.still_needed(cat, progress, read_pulls(st), away),
                               base=st.base_amounts())

    @app.get("/api/materials")
    def materials() -> dict:
        """Every build material against one full build, synthesis counted (D45 decision 9)."""
        st = Store(db())
        try:
            cat = catalogue.get()
            inventory = build_inventory(st, cat)
            away = hidden(st)
            groups = material_groups(st, cat, inventory)
            owned = {i.name: i.count or 0 for i in inventory if i.name}
            return {
                "groups": [g.as_dict() for g in groups],
                # the targets the user set themselves, so the page can offer to
                # put all of them back at once (D87)
                "by_hand": sorted(st.material_targets()),
                # one full build's EXP too: a resonator and a 5-star weapon, 1 -> 90 (D52)
                "exp": {kind: exp.cost(cat, kind, *exp.FULL[kind][:3], owned)
                        for kind in ("resonator", "weapon", "echo")},
                "builds": {k: sum(1 for n, b in v.items()
                                  if b.get("materials") and n not in away)
                           for k, v in cat.builds.items()},
                "monitor_port": LIVE_PORT,
            }
        finally:
            st.close()

    @app.post("/api/materials/preset")
    def set_material_preset(pick: MaterialPreset) -> dict:
        """Stock a whole family for one character, one weapon, or both (D88).
        `preset: null` puts the family back to what the builds ask for."""
        st = Store(db())
        try:
            cat = catalogue.get()
            if pick.preset is None:
                values: dict[str, int | None] = dict.fromkeys(family(cat, pick.name))
            elif pick.preset in PRESETS:
                values = dict(preset(cat, pick.name, pick.preset, hidden(st)))
            else:
                raise HTTPException(400, f"preset must be one of {list(PRESETS)} or null")
            for n, v in values.items():
                st.set_material_target(n, v)
            return {"name": pick.name, "targets": values}
        finally:
            st.close()

    @app.post("/api/scans/wipe")
    def wipe_scans() -> dict:
        """Start the scans over: back up, then forget every scan (D99).

        Kept: targets, plans, resonator progress, the pull history, settings and
        learned dishes. The database and the scan crops are MOVED aside under
        data/backups/<time>/ first, so a wipe can be undone by hand.
        """
        folder = db_path.parent / "backups" / datetime.now().strftime("%Y%m%d-%H%M%S")
        st = Store(db())
        try:
            st.backup_to(folder / db_path.name)
            icons = st.icon_dir
            if any(icons.iterdir()):
                shutil.move(str(icons), str(folder / "icons"))
            return {"removed": st.wipe_scans(), "backup": folder.as_posix()}
        finally:
            st.close()

    @app.post("/api/materials/targets/reset")
    def clear_material_targets() -> dict:
        """Put every hand-set material target back to what the builds ask for (D87)."""
        st = Store(db())
        try:
            return {"cleared": st.clear_material_targets()}
        finally:
            st.close()

    @app.post("/api/cooking/target")
    def set_target(fix: TargetFix) -> dict:
        st = Store(db())
        try:
            st.set_craft_target(fix.name, fix.target)
        finally:
            st.close()
        return {"name": fix.name, "target": fix.target}

    @app.post("/api/cooking/default")
    def set_default(fix: DefaultTarget) -> dict:
        if fix.type not in TYPES:
            raise HTTPException(400, f"type must be one of {TYPES}")
        st = Store(db())
        try:
            st.set_setting(f"target:{fix.type}", str(fix.target))
        finally:
            st.close()
        return {"type": fix.type, "target": fix.target}

    @app.post("/api/cooking/learned")
    def set_learned(fix: Learned) -> dict:
        st = Store(db())
        try:
            st.set_learned(fix.recipe, fix.learned)
        finally:
            st.close()
        return {"recipe": fix.recipe, "learned": fix.learned}

    @app.get("/api/inventory")
    def inventory(show_all: bool = False) -> dict:
        """What is owned now, merged from every scan (D45 decisions 3, 5, 13)."""
        st = Store(db())
        try:
            items = build_inventory(st, catalogue.get(), show_all=show_all)
            return {
                "tabs": tab_summary(st),
                "items": [i.as_dict() for i in items],
                "wallet": st.wallet(),
                "monitor_port": LIVE_PORT,
            }
        finally:
            st.close()

    @app.get("/api/item")
    def item_detail(name: str | None = None, ident: str | None = None) -> dict:
        """Everything the detail panel shows about one item, from any page (D45).

        Catalogue fields, what it is made of and used in (each with the owned
        count), the user's own reading of it, and -- for a dish or potion -- its
        cooking state (target, can make now, 食谱). `ident` finds an unnamed item.
        """
        if not name and not ident:
            raise HTTPException(400, "name or ident required")
        st = Store(db())
        try:
            cat = catalogue.get()
            inventory = build_inventory(st, cat)
            mine = next((i for i in inventory if (ident and i.ident == ident)
                         or (name and i.name == name)), None)
            name = name or (mine.name if mine else None)
            owned = {i.name: i.count or 0 for i in inventory if i.name}
            detail = cat.detail(name) if name else {"name": None, "page": {}, "used_in": []}
            for m in detail["page"].get("所需材料") or []:
                m["owned"] = owned.get(m["name"], 0)
            for u in detail["used_in"]:
                u["owned"] = owned.get(u["name"], 0)
            cooking = None
            if name and any(c["name"] == name for c in cat.craftables()):
                cooking = next(c.as_dict() for c in dishes_of(st, cat, inventory)
                               if c.name == name)
            material = None
            progress = progress_of(st)
            maxed = roster.finished(cat, progress)
            away = hidden(st)
            used = users(cat, name, maxed, away, progress) if name else {}
            eaten = cooking_needs(st, cat, inventory) if name else {}
            # A build material, or an ingredient a dish below its target is waiting
            # for, or anything the user gave a target: all of them have a number on
            # 材料, and the panel has to be able to say where it comes from (D122).
            bases = st.base_amounts()
            if used or eaten.get(name or "") or name in st.material_targets() or name in bases:
                wear_faces(used.get("resonators", []), faces_by_name(st))
                done = {t["tab"] for t in tab_summary(st) if t["complete"]}
                groups = build_materials(cat, inventory, complete_tabs=done, done=maxed,
                                         extra=eaten, skip=away,
                                         wanted=st.material_targets(),
                                         still=roster.still_needed(cat, progress, read_pulls(st),
                                                                   away),
                                         base=bases)
                # Which of those weapons the user actually has: the ones they do
                # come first, the rest go quiet at the end (D78).
                have, _ = weapons_mod.owned_counts(st, (read_pulls(st) or {}).get("weapons"))
                for row in used.get("weapons", []):
                    row["owned_count"] = have.get(row["name"], 0)
                    row["owned"] = row["owned_count"] > 0
                material = next((
                    {**t, "users": used}
                    for g in groups for t in g.as_dict()["tiers"] if t["name"] == name), None)
                if material is not None:
                    material["why"] = why(st, cat, name, inventory, maxed, away, progress)
                    # the family as one set (D88): each preset's numbers for every
                    # tier, and where each tier's target stands now
                    tiers = {t["name"]: t for g in groups for t in g.as_dict()["tiers"]}
                    members = family(cat, name)
                    material["set"] = {
                        "tiers": [{"name": n, "rarity": tiers.get(n, {}).get("rarity", 0),
                                   "icon_file": cat.icon_file(n),
                                   "target": tiers.get(n, {}).get("target", 0),
                                   "by_hand": tiers.get(n, {}).get("by_hand", False)}
                                  for n in members],
                        "presets": {k: preset(cat, name, k, away) for k in PRESETS},
                    }
            weapon = (roster.weapon(cat, inventory, name, done_tabs(st), read_pulls(st),
                                    skip=away)
                      if name else None)
            if weapon is not None:
                with_scan(st, [weapon])  # levels and holders from the 武器 tab (D62)
            people = cat.builds.get("resonators", {})
            if cooking and cooking.get("signature"):
                # the cook as a picture, not only "使用清宵烹饪蟹烧鱼有概率获得"
                cook = cooking["signature"].get("character")
                if cook in people:
                    cooking["signature"]["who"] = roster.avatar(cat, cook, people[cook])
                base = cooking["signature"].get("base")
                cooking["signature"]["base_icon"] = cat.icon_file(base) if base else None
                cooking["signature"]["base_rarity"] = (cat.entry(base or "") or {}).get("rarity")
            # a base dish: the characters' own versions of it
            variants = [
                {"name": d["name"], "icon_file": cat.icon_file(d["name"]),
                 "owned": owned.get(d["name"], 0),
                 "who": (roster.avatar(cat, cook, people[cook]) if cook in people
                         else {"name": cook})}
                for cook, dishes in roster.signature_dishes(cat).items()
                for d in dishes if name and d["base"] == name
            ]
            # how many pictures the scanners learned under this name: 识别记录 (D166)
            learned = st.conn.execute(
                "SELECT COUNT(*) FROM gallery WHERE item_name = ? "
                "AND (tab IS NULL OR tab != 'reference')", (name,)).fetchone()[0]
            return {**detail, "english": cat.english(name), "recognized": learned,
                    "item": mine.as_dict() if mine else None, "cooking": cooking,
                    "material": material, "weapon": weapon, "wallet": st.wallet(),
                    "variants": variants,
                    # an EXP item: how far everything owned of its kind goes (D157)
                    "exp": exp.worth(cat, name, owned) if name else None,
                    # where it is sold: how many, for how much (D158) -- and the least
                    # the user wants to keep of it, with one round of buying towards that
                    "shops": cat.sold(name) if name else [],
                    # a 密音筒's base is the echoes' (D161): no round, the gap instead
                    **({"base": st.echo_base() or None, "buy": None,
                        "echo": shops_mod.echo_gap(cat, owned, st.echo_base())}
                       if name and exp.kind_of(cat, name) == "echo" else
                       {"base": bases.get(name or ""), "echo": None,
                        "buy": next((row for row in shops_mod.to_buy(
                            cat, owned, {name: bases[name]} if name in bases else {})), None)})}
        finally:
            st.close()

    @app.get("/api/hover")
    def hover(name: str) -> dict:
        """The small card shown on hover (D49): owned, the family's tiers with owned
        counts, 周本/BOSS/特产 and who drops it, where to get it -- no panel needed."""
        from ..materials import families, role_of

        st = Store(db())
        try:
            cat = catalogue.get()
            inventory = build_inventory(st, cat)
            # A weapon is not a bag item: what it owns is copies, each with its
            # own 谐振阶数 and holder (D67).
            weapon = None
            if name in cat.builds.get("weapons", {}):
                mine = weapons_mod.by_weapon(st).get(name, [])
                weapon = {
                    **weapons_mod.summary(mine),
                    "copies": [
                        {**c.as_dict(),
                         "holder_icon": face_file(st, cat, c.holder)}
                        for c in mine
                    ],
                }
        finally:
            st.close()
        owned = {i.name: i.count or 0 for i in inventory if i.name}
        chain = next((c for c in families(cat) if name in c), [name])
        role, drop = role_of(cat, name)
        entry = cat.entry(name) or {}
        page = cat.page(name)
        return {
            "name": name, "rarity": entry.get("rarity") or 0, "owned": owned.get(name),
            "icon_file": cat.icon_file(name), "role": role, "drop": drop,
            "drop_icon": cat.bosses.get(drop or ""),
            "type": page.get("类型"), "source": (page.get("获取途径") or "").strip()[:80] or None,
            "family": [{"name": n, "rarity": (cat.entry(n) or {}).get("rarity") or 0,
                        "owned": owned.get(n), "icon_file": cat.icon_file(n)}
                       for n in chain] if len(chain) > 1 else [],
            "exp": exp.worth(cat, name, owned),
            # a dish or potion: each 材料 it needs per serving, against what is owned
            "ingredients": [
                {"name": m["name"], "amount": m["amount"], "owned": owned.get(m["name"], 0),
                 "icon_file": m.get("icon_file"), "rarity": m.get("rarity") or 0}
                for m in cat.detail(name)["page"].get("所需材料") or []
            ],
            "weapon": weapon,
        }

    @app.post("/api/materials/target")
    def set_material_target(fix: TargetFix) -> dict:
        """Keep N of something because YOU want to (D84): a target of your own,
        for a material no current build asks for. `target: null` goes back to the
        builds -- the same shape the dish targets use, and the same table."""
        st = Store(db())
        try:
            st.set_material_target(fix.name.strip(), fix.target)
            return {"name": fix.name, "target": fix.target}
        finally:
            st.close()

    @app.get("/api/shops")
    def shop_list() -> dict:
        """Every shop and what it sells, with what is owned of each good and the
        base amount it was given (D160): the 商店 page. `echo`: the tubes' gap to
        theirs, which is counted in echoes (D161)."""
        st = Store(db())
        try:
            cat = catalogue.get()
            owned = {i.name: i.count or 0
                     for i in build_inventory(st, cat) if i.name}
            bases = {**st.base_amounts(), shops_mod.ECHOES: st.echo_base()}
            return {"shops": shops_mod.listing(cat, owned, bases),
                    "echo": shops_mod.echo_gap(cat, owned, st.echo_base()),
                    "wallet": st.wallet(), "monitor_port": LIVE_PORT}
        finally:
            st.close()

    @app.post("/api/shops/bases")
    def set_base_amounts(fix: BaseFix) -> dict:
        """One base amount for several things at once (D160): what the right-click
        menu on picked tiles sends. Things no shop sells are left out, and said."""
        cat = catalogue.get()
        names = [n.strip() for n in fix.names]
        sold = [n for n in names if _keeps_base(cat, n)] if fix.target else names
        st = Store(db())
        try:
            for name in sold:
                st.set_base_amount(_base_key(cat, name), fix.target)
            return {"set": sold, "skipped": [n for n in names if n not in sold],
                    "base": fix.target or None}
        finally:
            st.close()

    @app.post("/api/shops/base")
    def set_base_amount(fix: TargetFix) -> dict:
        """The least to keep of something a shop sells (D158): a floor of the user's
        own under its target, which stays what it was. `target: null` (or 0) takes
        it away. Only for what a shop sells, and the 密音筒 (D161): anything else has
        its target (D84)."""
        name = fix.name.strip()
        if fix.target and not _keeps_base(catalogue.get(), name):
            raise HTTPException(400, _said(
                "没有商店卖这个：用「目标」来设定想囤的数量。",
                "No shop sells this: set how many to keep with its target."))
        st = Store(db())
        try:
            # a 密音筒's number is the echoes': one for all four tubes (D161)
            st.set_base_amount(_base_key(catalogue.get(), name), fix.target)
            return {"name": name, "base": fix.target or None,
                    "echo": exp.kind_of(catalogue.get(), name) == "echo"}
        finally:
            st.close()

    @app.post("/api/counts")
    def fix_count(fix: CountFix) -> dict:
        st = Store(db())
        try:
            st.set_manual_count(fix.ident.strip(), fix.count)
        finally:
            st.close()
        return {"ident": fix.ident, "count": fix.count}

    def english_rows(cat: Catalogue) -> list[dict]:
        """Everything that has a name here, with its English name and where that came
        from (D163): the things in the bag, the resonators, the weapons, the shops."""
        rows = []
        builds = cat.builds
        weapons = set((builds.get("weapons") or {}).keys())
        for name in sorted(cat.names()):
            if name in weapons:
                continue
            entry = cat.entry(name) or {}
            icon = cat.icon_file(name)
            rows.append({"name": name, "kind": entry.get("tab") or "物品",
                         "rarity": entry.get("rarity") or 0,
                         "icon": f"/api/reference/{icon}" if icon else None})
        for name, build in sorted((builds.get("resonators") or {}).items()):
            icon = cat.avatar_file(name)
            rows.append({"name": name, "kind": "共鸣者", "rarity": int(build.get("rarity") or 0),
                         "icon": f"/api/avatar/{icon}" if icon else None})
        for name in sorted(weapons):
            entry, icon = cat.entry(name) or {}, cat.icon_file(name)
            rows.append({"name": name, "kind": "武器", "rarity": entry.get("rarity") or 0,
                         "icon": f"/api/reference/{icon}" if icon else None})
        for shop in cat.shops:
            rows.append({"name": shop["name"], "kind": "商店", "rarity": 0,
                         "icon": f"/api/shop/{shop['icon']}" if shop.get("icon")
                         else f"/api/shop/shop-{shop.get('kind') or 'general'}.webp"})
        seen = set()
        for row in rows:
            english, source = cat.english_names.get(row["name"], (None, None))
            row["english"], row["source"] = english, source
        return [r for r in rows if not (r["name"] in seen or seen.add(r["name"]))]

    @app.get("/api/english")
    def english_names() -> dict:
        """Every name and its English name, for the 更新 page's 英文名 (D163)."""
        cat = catalogue.get()
        from ..catalogue import CATALOGUE_DIR

        path = CATALOGUE_DIR / "english.json"
        said = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        return {"rows": english_rows(cat), "fetched_at": said.get("fetched_at"),
                "differs": said.get("differs") or {}}

    @app.post("/api/english")
    def set_english(fix: EnglishFix) -> dict:
        """Give a name its English name by hand, or take the hand's away (D163). Only
        for something that has a name here."""
        cat = catalogue.get()
        name = fix.name.strip()
        if name not in {r["name"] for r in english_rows(cat)}:
            raise HTTPException(400, _said("这里没有这个名字。", "There is no such name here."))
        data = read_overrides()
        english = " ".join((fix.english or "").split())
        if english:
            data["english"][name] = english
        else:
            data["english"].pop(name, None)
        write_overrides(data)
        catalogue.forget()             # read back at once, not in CATALOGUE_LOOK
        found = catalogue.get().english_names.get(name, (None, None))
        return {"name": name, "english": found[0], "source": found[1]}

    @app.get("/api/find")
    def find_keys() -> dict:
        """What a name can be typed as, for everything that is not a resonator or
        a weapon (D148): each item of the catalogue, each thing in the bag, each
        boss, the words a list is grouped by, and each shop by its names and where
        it is (D161). Those two carry their keys on
        their own rows (D136); an item has no row of its own in half the places
        its name is shown -- a dish's ingredient, a family's tier, a drop's boss --
        so the pages ask once for the whole table and look a name up in it."""
        st = Store(db())
        try:
            cat = catalogue.get()
            names = set(cat.names()) | {i.name for i in build_inventory(st, cat) if i.name}
        finally:
            st.close()
        names |= {item["name"] for item in cat.craftables() if item.get("name")}
        names |= {drop for name in cat.names() if (drop := role_of(cat, name)[1])}
        for builds in cat.builds.values():
            for build in builds.values():
                names |= {build.get(word) for word in ("type", "weapon", "element")} - {None, ""}
        for shop in cat.shops:
            names |= {shop["name"], *shop.get("also", [])}
            names |= {w for r in shop.get("regions") or [] for w in (r["country"], r["town"]) if w}
        from .. import search

        # and the English name, where there is one (D163); the English pages show it first
        # and the Chinese under it (D164), so every name that has one is sent with it
        return {"keys": {name: keys for name in sorted(names)
                         if (keys := search.keys(name, cat.english(name) or ""))},
                "english": {name: english
                            for name, (english, _) in sorted(cat.english_names.items()) if english}}

    @app.get("/api/tabs")
    def tabs() -> list[dict]:
        """Every scanned tab's newest scan."""
        st = Store(db())
        try:
            return tab_summary(st)
        finally:
            st.close()

    @app.get("/api/scan/latest")
    def latest(scan_id: int | None = None) -> dict:
        """The newest scan, or the one asked for (the `show` view of one scan)."""
        st = Store(db())
        try:
            scan = st.scan(scan_id) if scan_id is not None else st.latest_scan()
            if scan is None:
                return {"scan": None, "items": []}
            reference = name_to_file()
            items = []
            for row in st.unique_items(int(scan["id"])):
                item = dict(row)
                item["reference_file"] = reference.get(item.get("item_name") or "")
                items.append(item)
            scan_d = dict(scan)
            total = scan_d.get("header_total")
            scan_d["found_unique"] = len(items)
            scan_d["missing"] = (total - len(items)) if total is not None else None
            scan_d["named"] = sum(1 for i in items if i.get("item_name"))
            return {"scan": scan_d, "items": items}
        finally:
            st.close()

    @app.get("/api/reference/{filename}")
    def reference_icon(filename: str) -> FileResponse:
        """Serve catalogue art.

        Only files listed in the downloaded index are served, so a crafted
        filename cannot walk out of the reference directory.
        """
        allowed = set(name_to_file().values())
        if filename not in allowed:
            raise HTTPException(404, "unknown reference icon")
        path = reference_dir() / filename        # asked now (D188)
        if not path.exists():
            raise HTTPException(404, "missing reference icon")
        media = "image/png" if filename.endswith(".png") else "image/webp"
        return FileResponse(path, media_type=media)

    # compressed on the way out (D171): 库存's answer is 128 KB as JSON, ~20 KB gzipped. Not
    # the scan monitor's live picture (a stream that never ends) and not images.
    app.add_middleware(GZipMiddleware, minimum_size=1024, exclude_content_types=(
        *DEFAULT_EXCLUDED_CONTENT_TYPES, "multipart/x-mixed-replace", "image/jpeg",
        "image/png", "image/webp"))
    return app
