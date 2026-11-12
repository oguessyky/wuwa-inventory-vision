# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Download the pictures of every echo and every sonata set, for 计算 (D269).

Source: Kuro's wiki, the same API as tools/fetch_catalogue.py and the boss pictures (D54):
catalogue 1107 (the echoes, by the names the game gives them) and 1219 (the sets). Each entry's
square picture, resized to WebP by the wiki's CDN. Used locally only; never shipped.

Some echo entries carry a "共鸣回响·" in front of the game's name: both names point at the picture.

Output: data/catalogue/echoes/<entry id>.webp and data/catalogue/echoes.json
{"echoes": {name: file}, "sets": {name: file}}. Incremental: files on disk are not downloaded
again.

Run:  uv run python tools/fetch_echoes.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import fetch_pool
from fetch_builds import _download
from fetch_recipes import _post

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

ECHOES, SETS = 1107, 1219
OUT = Path("data/catalogue/echoes")
INDEX = Path("data/catalogue/echoes.json")
ICON_WIDTH = 160
DELAY_SECONDS = 0.3
PREFIX = "共鸣回响·"


def entries(catalogue_id: int) -> list[tuple[str, str, str]]:
    """(name, picture url, file) for every entry of a wiki catalogue that has a picture."""
    records = _post("getPage", {"catalogueId": catalogue_id, "page": 1, "limit": 1000})
    out = []
    for record in records["results"]["records"]:
        name = (record.get("name") or "").strip()
        url = (record.get("content") or {}).get("contentUrl")
        if name and url:
            out.append((name, url, f"{record['id']}.webp"))
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    index: dict[str, dict[str, str]] = {"echoes": {}, "sets": {}}
    jobs = [("echoes", *e) for e in entries(ECHOES)] + [("sets", *e) for e in entries(SETS)]
    for (kind, name, _url, _file), saved, error in fetch_pool.each(
        jobs, lambda job: _download(job[2], OUT / job[3], ICON_WIDTH), pause=DELAY_SECONDS
    ):
        if error is not None:
            raise error
        index[kind][name] = saved
        if kind == "echoes" and name.startswith(PREFIX):
            index[kind].setdefault(name[len(PREFIX) :], saved)
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(index['echoes'])} echo pictures, {len(index['sets'])} set icons -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
