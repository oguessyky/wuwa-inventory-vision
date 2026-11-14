# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Download Kuro's official guide (D313): each resonator's guide articles, read into echo plans,
substat order, stats to reach and weapons (`wuwa_vision.guides`).

Source: the guide server behind wuwaguide.kurogames.com. Asked as a browser asks it -- the user
said so: "you must use like normal https request with Mozilla, no more any stated with the project
name". Only what changed since the last fetch is asked again (each article's `modifiedAt`).

A few at a time, each worker keeping its connection as a browser does; a request the server cut
is asked again later while the others go on (D324).

Run from the main app's 更新 page (D46) -- only when its button is pressed -- or by hand.

Output: data/catalogue/guides.json.

Run:  uv run python tools/fetch_guides.py [--force]
"""

from __future__ import annotations

import argparse
import http.client
import json
import sys
import threading
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import fetch_pool  # noqa: E402

from wuwa_vision import guides  # noqa: E402

HOST = "guide-server.aki-game.net"
BASE = "https://" + HOST
#: A browser's own: nothing of this project is named.
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept": "application/json, text/plain, */*",
           "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8", "x-language": "zh-Hans",
           "Referer": "https://wuwaguide.kurogames.com/",
           "Origin": "https://wuwaguide.kurogames.com"}
OUT = Path("data/catalogue") / guides.NAME
#: A breath between a worker's asks: the site is a person's, not a feed.
PAUSE = 0.25
#: How long one answer may take before it is given up and asked again later.
TIMEOUT = 30
#: Fewer at once than the wiki's six: it is one person's site.
AT_ONCE = 3

#: Each worker's own kept connection.
_local = threading.local()


def _connection() -> tuple[http.client.HTTPSConnection, bool]:
    """This worker's connection, and whether it was kept from an earlier ask."""
    kept = getattr(_local, "connection", None)
    if kept is not None:
        return kept, True
    _local.connection = http.client.HTTPSConnection(HOST, timeout=TIMEOUT)
    return _local.connection, False


def _drop() -> None:
    connection = getattr(_local, "connection", None)
    _local.connection = None
    if connection is not None:
        connection.close()


def _get(path: str, language: str = "zh-Hans", **params: object) -> object:
    target = path + ("?" + urllib.parse.urlencode(params) if params else "")
    headers = {**HEADERS, "x-language": language}
    while True:
        connection, kept = _connection()
        try:
            connection.request("GET", target, headers=headers)
            response = connection.getresponse()
            body = response.read()
            break
        except (http.client.RemoteDisconnected, ConnectionResetError, BrokenPipeError):
            _drop()
            if not kept:  # a new connection cut at once is a failure; a kept one had gone idle
                raise
        except BaseException:
            _drop()
            raise
    if response.status != 200:
        _drop()
        raise http.client.HTTPException(f"{path}: HTTP {response.status}")
    said = json.loads(body)
    if said.get("code") != 200:
        raise RuntimeError(f"{path}: {said.get('message')}")
    return said.get("data")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="ask every article again")
    args = parser.parse_args()
    have = {} if args.force else guides.load(OUT.parent).get("roles") or {}
    kept = {a["id"]: a for entry in have.values() for a in entry.get("articles") or []}
    named = [(name, role) for role in _get("/role/avatar/list") or []
             if (name := guides._zh(role.get("texts")))]
    failed = asked = 0

    def listing(job: tuple[str, dict]) -> list:
        return _get("/introduction/list", roleGbId=job[1]["roleGbId"]) or []

    lists: dict[str, list] = {}
    for (name, _role), listed, error in fetch_pool.each(named, listing, at_once=AT_ONCE,
                                                        pause=PAUSE):
        if error is None:
            lists[name] = listed
        else:  # one resonator's failure is said, the rest go on
            print(f"FAILED {name}: {error}", flush=True)
            failed += 1

    def unchanged(item: dict) -> bool:
        old = kept.get(item.get("id"))
        return bool(old) and old.get("modified") == item.get("modifiedAt")

    todo = [(name, item) for name, listed in lists.items() for item in listed
            if not unchanged(item)]

    def read(job: tuple[str, dict]) -> dict:
        # asked in the language it is written in: in any other the server has nothing
        lang = guides.language(job[1])
        said = guides.article(_get("/introduction/info", language=lang, id=job[1]["id"]))
        # the article's own answer has no modifiedAt: the list's is what the next run compares
        return {**said, "modified": job[1].get("modifiedAt"), "language": lang}

    fresh: dict[object, dict] = {}
    for (name, item), said, error in fetch_pool.each(todo, read, at_once=AT_ONCE, pause=PAUSE):
        if error is None:
            fresh[item.get("id")] = said
            asked += 1
        else:
            print(f"FAILED {name} {item.get('id')}: {error}", flush=True)
            failed += 1

    roles: dict[str, dict] = {}
    for name, role in named:  # in the server's own order, whatever order the answers came in
        if name not in lists:
            if name in have:
                roles[name] = have[name]
            continue
        articles = []
        for item in lists[name]:
            article = fresh.get(item.get("id")) or kept.get(item.get("id"))
            if article:
                articles.append(article)
        roles[name] = {"id": role.get("roleGbId"), "articles": articles}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"roles": roles}, ensure_ascii=False, indent=1), encoding="utf-8")
    total = sum(len(e["articles"]) for e in roles.values())
    print(f"{len(roles)} resonators, {total} guides (fetched={asked} failed={failed}) -> {OUT}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
