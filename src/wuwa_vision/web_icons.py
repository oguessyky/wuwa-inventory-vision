# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""The pages' item icons as WebP; the catalogue itself stays PNG (D230).

The user, 2026-10-28: "help me to do the webp conversion including the server part and full part
that they will show which mean it would just left png for the scanner and the copy inside the NAS
to send to the scanner". Measured on their data: 库存 fetched 15.6 MB of PNG icons, 3.9 MB as WebP
-- on a phone over 4G, 8.3 s -> 2.1 s.

- **The copies are made once and kept beside**, in a folder of their own (`data/catalogue-web/`)
  that a scanner's sync never sees: what a scanner is sent, and embeds to recognise items, stays
  the wiki's PNG.
- **Only a machine that serves the pages makes them**: `wuwa serve` (the server, the full
  package) starts it, and a wiki update runs it again. A scanner never serves, so it makes none.
- **Until a copy is made, the page gets the PNG**: nothing waits, nothing breaks.
- Quality 90, method 4: all 614 icons in ~10 s on a PC, about a quarter of the PNG; method 6
  took 60x as long for 1% less.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

from PIL import Image

QUALITY = 90
METHOD = 4
log = logging.getLogger(__name__)

_lock = threading.Lock()
_active: Path | None = None        # the catalogue whose copies this process keeps, once started
_again = threading.Event()


def web_dir(catalogue_dir: Path) -> Path:
    """Where a catalogue's WebP copies are: beside it, never in it (`data/catalogue-web`)."""
    catalogue_dir = Path(catalogue_dir)
    return catalogue_dir.with_name(catalogue_dir.name + "-web")


def copy_for(png: Path) -> Path | None:
    """The WebP copy of one of the catalogue's PNGs, if it is made and not older than the PNG."""
    png = Path(png)
    if png.suffix.lower() != ".png":
        return None
    copy = web_dir(png.parent) / f"{png.stem}.webp"
    try:
        return copy if copy.stat().st_mtime >= png.stat().st_mtime else None
    except OSError:
        return None


def make_copies(catalogue_dir: Path) -> tuple[int, int]:
    """Make the copies that are missing or older than their PNG, and remove those whose PNG is
    gone. Returns (made, removed). Each copy is written whole and then put in place, so a page
    never gets half of one."""
    catalogue_dir = Path(catalogue_dir)
    out = web_dir(catalogue_dir)
    pngs = {p.stem: p for p in catalogue_dir.glob("*.png") if p.is_file()}
    made = removed = 0
    if pngs:
        out.mkdir(parents=True, exist_ok=True)
    for stem, png in sorted(pngs.items()):
        if copy_for(png) is not None:
            continue
        target = out / f"{stem}.webp"
        # a name of its own: several processes may make the same copy at once (the browser
        # suite starts four servers on one catalogue), and each puts a whole file in place
        part = out / f".{stem}.{os.getpid()}.{threading.get_ident()}.part"
        try:
            with Image.open(png) as image:
                image.save(part, "WEBP", quality=QUALITY, method=METHOD)
            part.replace(target)
            made += 1
        except (OSError, ValueError) as exc:      # an icon that cannot be read: the PNG is served
            log.warning("webp copy of %s not made: %s", png.name, exc)
            part.unlink(missing_ok=True)
    if out.is_dir():
        for copy in out.glob("*.webp"):
            if copy.stem not in pngs:
                copy.unlink(missing_ok=True)
                removed += 1
    return made, removed


def _kick() -> None:
    """Run the copies in the background unless they are running already; whoever runs them
    looks again on the way out, so a refresh that came meanwhile is never lost."""
    if not _lock.acquire(blocking=False):
        return

    def run() -> None:
        try:
            while _again.is_set() and _active is not None:
                _again.clear()
                made, removed = make_copies(_active)
                if made or removed:
                    log.info("pages' icons as WebP: %d made, %d removed", made, removed)
        finally:
            _lock.release()
        if _again.is_set():
            _kick()

    threading.Thread(target=run, name="web-icons", daemon=True).start()


def start(catalogue_dir: Path) -> None:
    """Keep this catalogue's copies from now on, and make what is missing in the background."""
    global _active
    _active = Path(catalogue_dir)
    refresh()


def refresh() -> bool:
    """Make the copies again (after a wiki update), in the background. Does nothing, and says
    so, where `start` was never called: a scanner, or a test."""
    if _active is None:
        return False
    _again.set()
    _kick()
    return True


def stop() -> None:
    """Keep no catalogue's copies any more (for tests)."""
    global _active
    _active = None
