# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Which release changed what, on which side: the scanner, the server (PLAN.md D197; D225).

The home updates with one button in a NAS's Docker app; the scanner is a zip. The two drift
apart, and a release often changes only one of them. So each release lists its changes per
side, and whichever side is newer knows the whole list: an older side is told to update only
when it is missing something of its own, and told what.

Nothing here stops a sync. Whether two versions can talk at all is `sync.PROTOCOL`; this is
only advice. Headless: the terminal, the scan's page and the home's pages word it themselves.
"""

from __future__ import annotations

import json
import re
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: Newest first, read from releases.json -- which the help site reads too, for its page of every
#: version (D227). Every release has its entry (tests/test_versions.py), and a release that
#: changed nothing on a side says so with an empty list: that side need not be updated. The
#: server's side is keyed "home", its name before 1.2.0, which every scanner since 1.1.1 reads.
RELEASES: tuple[dict, ...] = tuple(
    json.loads((Path(__file__).with_name("releases.json")).read_text("utf-8"))["releases"])

#: Scanners up to this one sent no version: a scan the home holds without one came from
#: this release or an older one.
SILENT_UNTIL = "1.1.0"

_NUMBER = re.compile(r"v?(\d+)\.(\d+)\.(\d+)")


def parse(text: str | None) -> tuple[int, int, int] | None:
    """(1, 1, 0) from "1.1.0", "v1.1.0  4cbb9e9  2026-10-26" or "1.0.4-rc1"; else None."""
    hit = _NUMBER.match((text or "").strip())
    return tuple(int(n) for n in hit.groups()) if hit else None  # type: ignore[return-value]


def plain(text: str | None) -> str | None:
    """"1.1.0" from any way a version is written; None when it is not one."""
    found = parse(text)
    return ".".join(map(str, found)) if found else None


def this_version() -> str | None:
    """This copy's version: a release's or a home image's VERSION file, else the installed
    package's. None when neither says."""
    path = ROOT / "VERSION"
    if path.is_file() and plain(path.read_text(encoding="utf-8")):
        return plain(path.read_text(encoding="utf-8"))
    try:
        return plain(metadata.version("wuwa-vision"))
    except metadata.PackageNotFoundError:
        return None


def merged(*lists) -> tuple[dict, ...]:  # noqa: ANN002 -- several RELEASES-shaped lists
    """Both sides' lists as one, newest first: the newer side knows releases the older does not."""
    by_version: dict[tuple[int, int, int], dict] = {}
    for releases in lists:
        for release in releases or ():
            key = parse(release.get("version"))
            if key is not None:
                by_version.setdefault(key, release)
    return tuple(by_version[k] for k in sorted(by_version, reverse=True))


def _between(releases, low: tuple, high: tuple, side: str) -> list[dict]:  # noqa: ANN001
    """The changes on `side` of every release after `low`, up to and including `high`."""
    return [{**change, "version": r["version"]} for r in releases
            if low < (parse(r["version"]) or (0, 0, 0)) <= high for change in r.get(side) or ()]


def compare(mine: str | None, theirs: str | None, side: str,
            releases=RELEASES) -> dict:  # noqa: ANN001
    """What `side` ("scanner" or "home") on `mine` should know about the other on `theirs`.

    `update`: "mine", "theirs" or None -- which side is missing changes of its own.
    `missing`: those changes, newest first. `newer`: which side is ahead, if either. A
    scanner that sent no version (`theirs` None, on a home) is taken as SILENT_UNTIL.
    """
    other = "home" if side == "scanner" else "scanner"
    if theirs is None and side == "home":
        theirs = SILENT_UNTIL
    a, b = parse(mine), parse(theirs)
    said = {"mine": mine, "theirs": theirs, "side": side, "newer": None, "update": None,
            "missing": []}
    if a is None or b is None or a == b:
        return said
    if a < b:
        said["newer"] = "theirs"
        said["missing"] = _between(releases, a, b, side)
        said["update"] = "mine" if said["missing"] else None
    else:
        said["newer"] = "mine"
        said["missing"] = _between(releases, b, a, other)
        said["update"] = "theirs" if said["missing"] else None
    return said


def say(said: dict) -> str:
    """One line for the terminal and the scan's page; "" when there is nothing to say."""
    me, them = ("扫描端", "服务器") if said["side"] == "scanner" else ("服务器", "扫描端")
    if said["newer"] is None:
        return ""
    what = "；".join(c["zh"] for c in said["missing"][:3])
    more = f" 等 {len(said['missing'])} 项" if len(said["missing"]) > 3 else ""
    if said["update"] == "mine":
        return (f"{them} v{said['theirs']} 比这个{me} v{said['mine']} 新：建议更新{me}"
                f"（{what}{more}）")
    if said["update"] == "theirs":
        return (f"这个{me} v{said['mine']} 比{them} v{said['theirs']} 新：建议更新{them}"
                f"（{what}{more}）")
    newer, older = (them, me) if said["newer"] == "theirs" else (me, them)
    return f"{newer}较新（v{said['theirs'] if said['newer'] == 'theirs' else said['mine']}），" \
           f"但没有{older}这边的改动：{older}不用更新"
