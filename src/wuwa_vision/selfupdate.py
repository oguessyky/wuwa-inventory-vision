# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""The scanner updates itself to its home's version (PLAN.md D203).

The home updates with a button in a NAS's Docker app; the scanner was a zip to unpack by hand,
its data folder to move across. Now `wuwa update` (the package's 「4 更新 Update」) does it -- but
only when the home's version check (D197) says this copy misses changes of its own. Then, and
only on that click, it fetches the release of the home's version from the project's GitHub
releases: the release's checksums, then the package, checked against them. It unpacks over
this folder, and never touches the data folder, the environment or the Python running it.
Nothing is fetched otherwise (hard constraint 3; AGENTS.md lists this exception).
"""

from __future__ import annotations

import hashlib
import io
import shutil
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from . import versions

RELEASES_URL = "https://github.com/oguessyky/wuwa-inventory-vision/releases/download"
#: What an update never writes: the scans, the environment and the Python running it.
KEEP = ("data", ".venv", "python")
UA = "wuwa-vision-update"
TIMEOUT = 120


class UpdateError(RuntimeError):
    """Said to the user as it is."""


@dataclass(frozen=True)
class Plan:
    version: str
    zip_name: str
    base: str
    missing: list[dict] = field(default_factory=list)


def plan(mine: str | None, hello: dict, kind: str, platform: str) -> Plan | None:
    """The release to fetch, or None: only when the home says this copy is behind on its side."""
    theirs = versions.plain(hello.get("version"))
    said = versions.compare(mine, theirs, "scanner",
                            versions.merged(versions.RELEASES, hello.get("releases")))
    if said["update"] != "mine" or theirs is None:
        return None
    package = ("mac-" if platform == "darwin" else "") + kind
    return Plan(version=theirs, zip_name=f"wuwa-inventory-vision-{theirs}-{package}.zip",
                base=f"{RELEASES_URL}/v{theirs}/", missing=said["missing"])


def kind_of(root: Path) -> str:
    """"full" where the NAS files came along (the full program), else "scanner"."""
    return "full" if (root / "deploy" / "nas").is_dir() else "scanner"


def hint(said: dict) -> str:
    """What to do about a scanner that is behind, for the line before a scan."""
    if said.get("update") != "mine":
        return ""
    return "双击「4 更新 Update」即可更新（只下载主机那个版本）"


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310 -- https only
        return response.read()


def install(plan: Plan, root: Path, fetch: Callable[[str], bytes] = _get) -> dict:
    """Fetch the release, check it, and unpack it over `root`, keeping KEEP. Returns counts."""
    sums = fetch(plan.base + "SHA256SUMS.txt").decode("utf-8", "replace")
    want = next((line.split()[0] for line in sums.splitlines()
                 if line.split()[-1:] == [plan.zip_name]), None)
    if want is None:
        raise UpdateError(f"v{plan.version} 的发布里没有 {plan.zip_name}。")
    data = fetch(plan.base + plan.zip_name)
    if hashlib.sha256(data).hexdigest() != want:
        raise UpdateError("下载的文件和发布写的校验值对不上：没有更新任何东西。")
    files = 0
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for info in archive.infolist():
            parts = PurePosixPath(info.filename).parts[1:]      # under the package's one folder
            if info.is_dir() or not parts or parts[0] in KEEP or ".." in parts:
                continue
            dest = root.joinpath(*parts)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as src, dest.open("wb") as out:
                shutil.copyfileobj(src, out)
            files += 1
    return {"version": plan.version, "files": files}
