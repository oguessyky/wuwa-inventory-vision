# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Kuro's official guide (D313): each resonator's guide articles, as `tools/fetch_guides.py` keeps
them in guides.json beside the catalogue. Headless and pure: an article as the guide server
answers it is read into what 计算 uses -- its echo plans (the main echo, the sets and their pieces,
the main stat by cost), the substat order, the stats to reach, and the weapons in order.
"""

from __future__ import annotations

import collections
import html
import json
import re
from pathlib import Path

NAME = "guides.json"
_TAG = re.compile(r"<[^>]+>")


def _zh(texts: list[dict] | None, key: str = "name") -> str:
    """The Chinese of a list of texts by language, else the first there is."""
    texts = texts or []
    said = next((t for t in texts if t.get("language") == "zh-Hans"), texts[0] if texts else {})
    return str(said.get(key) or "")


def _plain(words: str) -> str:
    return html.unescape(_TAG.sub("", words or "")).strip()


def _plan(plan: dict | None) -> dict | None:
    if not plan:
        return None
    pieces: dict[str, int] = {}
    ids: dict[str, int | None] = {}
    for effect in plan.get("echoSetEffects") or []:
        name = _zh(effect.get("texts"))
        if name:
            # a set listed for its 2-piece and its 5-piece is one set, of the most
            pieces[name] = max(pieces.get(name, 0), int(effect.get("echoSet") or 0))
            # the game's own id of it: an article in another language names it in that language
            group = effect.get("echoSetGroupGameBusinessId")
            ids[name] = int(group) if group is not None else None
    mains: dict[str, list[str]] = {}
    for item in plan.get("echoAttributes") or []:
        stat = _zh((item.get("attribute") or {}).get("texts"))
        if stat:
            mains.setdefault(str(item.get("cost")), []).append(stat)
    return {"echo": _zh((plan.get("echoProps") or {}).get("texts")) or None,
            "sets": [{"set": n, "id": ids.get(n), "pieces": p} for n, p in pieces.items()],
            "mains": mains}


def article(info: dict) -> dict:
    """One article (`/introduction/info`), read."""
    echo = info.get("echo") or {}
    plans = [_plan(echo.get("main")), _plan(echo.get("spare"))]
    for mode in echo.get("modeEchoRecommends") or []:
        plans += [_plan(mode.get("main")), _plan(mode.get("spare"))]
    seen, kept = set(), []
    for plan in plans:
        key = json.dumps(plan, ensure_ascii=False, sort_keys=True)
        if plan and key not in seen:
            seen.add(key)
            kept.append(plan)
    base = info.get("baseTexts") or []
    return {
        "id": info.get("id"),
        "title": _zh(base, "introductionName"),
        "source": _zh(base, "introductionSource"),
        "plans": kept,
        "subs": _plain(_zh(info.get("echoTexts"), "recommendDescription")),
        "targets": [{"stat": _zh(i.get("texts")), "value": i.get("recommendAmount")}
                    for i in (info.get("roleAttribute") or {}).get("items") or []],
        "weapons": [{"name": _zh(i.get("texts")),
                     "id": int(i["gbId"]) if str(i.get("gbId") or "").isdigit() else None}
                    for i in (info.get("weapon") or {}).get("items") or []],
        "modified": info.get("modifiedAt"),
    }


def recommended_sets(entry: dict, names: dict[int, str] | None = None) -> list[str]:
    """A resonator's sets as their guides recommend them, the most named first (D313): by the
    game's id where `names` (id -> 计算's name) knows it, else as the article names it."""
    counts: collections.Counter[str] = collections.Counter()
    first: dict[str, int] = {}
    for one in entry.get("articles") or []:
        for plan in one.get("plans") or []:
            for worn in plan.get("sets") or []:
                name = (names or {}).get(worn.get("id")) or worn["set"]
                counts[name] += 1
                first.setdefault(name, len(first))
    return sorted(counts, key=lambda s: (-counts[s], first[s]))


def language(listed: dict) -> str:
    """The language an article is written in (D313): the one its title is in -- asked in any
    other, the server answers nothing."""
    for text in listed.get("texts") or []:
        if str(text.get("introductionName") or "").strip():
            return str(text.get("language") or "zh-Hans")
    return "zh-Hans"


def load(directory: Path) -> dict:
    """guides.json from the catalogue folder, or nothing when it has not been fetched."""
    try:
        return json.loads((Path(directory) / NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
