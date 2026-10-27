# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Which release changed what, on which side: the scanner, the home (PLAN.md D197).

The home updates with one button in a NAS's Docker app; the scanner is a zip. The two drift
apart, and a release often changes only one of them. So each release lists its changes per
side, and whichever side is newer knows the whole list: an older side is told to update only
when it is missing something of its own, and told what.

Nothing here stops a sync. Whether two versions can talk at all is `sync.PROTOCOL`; this is
only advice. Headless: the terminal, the scan's page and the home's pages word it themselves.
"""

from __future__ import annotations

import re
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: Newest first. Every release has its entry (tests/test_versions.py), and a release that
#: changed nothing on a side says so with an empty list: that side need not be updated.
RELEASES: tuple[dict, ...] = (
    {"version": "1.1.2", "date": "2026-10-27",
     "scanner": [],
     "home": [{"zh": "折叠屏和 300 像素宽的手机上，帮助、商店、我的共鸣者、版本列表和「这是谁」都排得整齐",
               "en": "on a folded phone and screens 300 px wide, Help, Shops, My resonators, the "
                     "version list and \"Who is this?\" read right"},
              {"zh": "下拉列表不会被会滚动的列表挡住；逐个命名悬停时不再变暗；数据页两个方块之间有间距",
               "en": "a dropdown is never cut off by a list that scrolls; Name them one by one no "
                     "longer dims under the pointer; the Data page's two boxes have a gap"}]},
    {"version": "1.1.1", "date": "2026-10-27",
     "scanner": [{"zh": "连接主机时比较两边的版本，说哪边该更新、缺什么",
                  "en": "compares versions with the home, and says which side to update and why"},
                 {"zh": "主机比较新时，双击「4 更新 Update」自己更新",
                  "en": "updates itself with 4 更新 Update when the home is newer"},
                 {"zh": "Mac 版程序包（mac-full、mac-scanner）",
                  "en": "packages for a Mac (mac-full, mac-scanner)"},
                 {"zh": "认得超级豹风雪；奇幻变奏不再没有名字；一模一样的物品不再拿来学习",
                  "en": "超级豹风雪 is named; 奇幻变奏 is no longer left unnamed; items drawn "
                        "exactly alike are not learned"}],
     "home": [{"zh": "总览说最新的扫描是哪个版本的扫描端做的；更新页列出每个版本改了哪边",
               "en": "Overview says which scanner version made the newest scans; Update lists "
                     "what each version changed on which side"},
              {"zh": "待确认的物品说它可能是哪几样，而不是说它们长得一模一样",
               "en": "an item waiting to be confirmed says what it could be, not that the "
                     "candidates look identical"},
              {"zh": "第一次下载图鉴快了几倍；钱包每种货币取各自最新的读数",
               "en": "the first catalogue download is several times faster; each wallet amount "
                     "is its own newest reading"},
              {"zh": "快速连点共鸣者进度会合起来保存；共鸣者和武器默认显示已拥有",
               "en": "quick clicks on a resonator's progress are saved together; Resonators and "
                     "Weapons open on Owned"},
              {"zh": "识别不列一模一样的物品，说明也改清楚了",
               "en": "Recognition leaves out items drawn exactly alike, and says better what "
                     "it is"}]},
    {"version": "1.1.0", "date": "2026-10-26",
     "scanner": [{"zh": "特殊料理不再认成原料理（青蔬蛋饼）",
                  "en": "special dishes are told from their base dish (青蔬蛋饼)"},
                 {"zh": "颜色挡掉了正确的图时改为待确认（千古洑流、气动阻抗喷雾）",
                  "en": "a tile whose right picture was shut out on colour waits for a click "
                        "(千古洑流, 气动阻抗喷雾)"},
                 {"zh": "数量相同的两个标签页不再合并；新物品第一次扫描就认识",
                  "en": "two tabs with the same count are kept apart; new items are known on "
                        "the first scan"},
                 {"zh": "扫描页显示还没扫描的标签；连接主机只要 wuwa-home",
                  "en": "the scan page shows the tabs not scanned yet; connecting takes just "
                        "wuwa-home"}],
     "home": [{"zh": "现成的 Docker 镜像；新主机在引导最后下载图鉴，"
                     "显示进度和剩余时间，失败自动重试",
               "en": "a ready-made Docker image; a new home downloads its catalogue at the end "
                     "of the guide, with progress, time left and retries"},
              {"zh": "批量标记已练满一次完成，进行中有提示",
               "en": "marking many resonators is one quick save that says it is working"}]},
    {"version": "1.0.3", "date": "2026-10-25",
     "scanner": [{"zh": "维基更新后的新物品第一次扫描就认识",
                  "en": "new items from a wiki update are known on the first scan"}],
     "home": [{"zh": "总览显示商店位置和低于目标的材料；待确认一键找到；规划成为日常页",
               "en": "Overview shows where shops are and materials below target; items to "
                     "confirm are found in one click; Planner is a daily page"}]},
    {"version": "1.0.2", "date": "2026-10-20",
     "scanner": [{"zh": "第一个公开版本", "en": "the first public release"}],
     "home": [{"zh": "第一个公开版本", "en": "the first public release"}]},
)

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
    me, them = ("扫描端", "主机") if said["side"] == "scanner" else ("主机", "扫描端")
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
