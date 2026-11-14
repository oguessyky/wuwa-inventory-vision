# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""The pages in the user's own order (D321): what 设置 saves and every page is drawn with.

The column (web/src/components/Shell.tsx) draws the pages in two groups: 日常, which a phone
keeps in its bottom bar, and 管理. The user may order both, move pages between them and hide
some. The order is kept in the app's database (``app_setting`` ``nav``), not the browser: the
same app is opened from the PC and from a phone over the tailnet (D108), two browsers.
"""

from __future__ import annotations

import json

#: Every page of the order, as the column ships them (Shell.tsx PAGES).
PAGES = ("/", "/planner", "/cooking", "/materials", "/resonators", "/weapons", "/calc", "/sets",
         "/shops", "/inventory", "/guess", "/update")
#: 日常 as shipped (Shell.tsx MAIN_PAGES): the phone's bottom bar (D131, D159, D182).
DAILY = ("/", "/planner", "/cooking", "/materials", "/resonators")
#: At most this many in 日常: the phone's bar has room for five.
MOST_DAILY = 5
#: Where it is kept.
SETTING = "nav"


class NavError(ValueError):
    """An order that cannot be kept, with what is wrong, in both languages."""

    def __init__(self, zh: str, en: str) -> None:
        super().__init__(en)
        self.zh, self.en = zh, en


def default() -> dict[str, list[str]]:
    """The order the app ships with."""
    return {"daily": list(DAILY), "manage": [p for p in PAGES if p not in DAILY], "hidden": []}


def check(order: dict) -> dict[str, list[str]]:
    """An order sent from 设置, as it will be kept; NavError if it is not one.

    Every page exactly once, in one of the two groups; one to five in 日常, at least one of them
    shown (or a phone has no bar); only pages there are hidden."""
    daily, manage, hidden = (list(order.get(k) or []) for k in ("daily", "manage", "hidden"))
    named = daily + manage
    unknown = [p for p in named + hidden if p not in PAGES]
    if unknown:
        raise NavError(f"没有这个页面：{unknown[0]}", f"There is no such page: {unknown[0]}")
    twice = sorted({p for p in named if named.count(p) > 1})
    if twice:
        raise NavError(f"页面出现了两次：{twice[0]}", f"A page is there twice: {twice[0]}")
    missing = [p for p in PAGES if p not in named]
    if missing:
        raise NavError(f"少了页面：{missing[0]}", f"A page is missing: {missing[0]}")
    if len(daily) > MOST_DAILY:
        raise NavError("日常最多五个页面", "Daily holds five pages at most")
    if not [p for p in daily if p not in hidden]:
        raise NavError("日常至少要显示一个页面", "Daily must show at least one page")
    return {"daily": daily, "manage": manage, "hidden": [p for p in PAGES if p in hidden]}


def mend(kept: dict) -> dict[str, list[str]]:
    """An order saved by an earlier version, made whole: a page that is no longer one is dropped,
    a page added since goes at the end of the group it ships in (管理 when 日常 is full)."""
    daily = [p for p in dict.fromkeys(kept.get("daily") or []) if p in PAGES]
    manage = [p for p in dict.fromkeys(kept.get("manage") or []) if p in PAGES and p not in daily]
    for page in PAGES:
        if page in daily or page in manage:
            continue
        (daily if page in DAILY and len(daily) < MOST_DAILY else manage).append(page)
    hidden = [p for p in PAGES if p in (kept.get("hidden") or [])]
    return check({"daily": daily[:MOST_DAILY], "manage": daily[MOST_DAILY:] + manage,
                  "hidden": hidden})


def read(value: str | None) -> dict:
    """The order kept as ``value`` (None: none kept), and whether it is the user's own."""
    if value:
        try:
            order = mend(json.loads(value))
        except (ValueError, TypeError, AttributeError):
            order = None                        # unreadable: the shipped one, not a broken page
        if order is not None:
            return {**order, "custom": order != default()}
    return {**default(), "custom": False}


def script(said: dict) -> str:
    """The order as the server puts it into a page (D321), or nothing for the shipped one."""
    if not said.get("custom"):
        return ""
    body = json.dumps(said, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'<script id="nav-order" type="application/json">{body}</script>'
