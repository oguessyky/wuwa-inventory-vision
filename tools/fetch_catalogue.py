# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Download the official Chinese item catalogue: names, rarities, icons.

Source: Kuro's own wiki (库街区 鸣潮WIKI, wiki.kurobbs.com). Its public API
`api.kurobbs.com/wiki/core/catalogue/item/getPage` lists every entry of a
catalogue category with the in-game Chinese name, the rarity (`star`) and a
256x256 transparent icon on Kuro's CDN.

Why this replaced the first icon tool (another site's set, English names; removed in D133):
* The detail panel is Chinese, and its OCR drops rare characters at full
  confidence (改造镣环 -> 改造环 at 1.00). Snapping a read onto the real names
  fixes that (D42); English names cannot.
* `star` is the item's rarity, so rarity gating is exact instead of inferred from
  LF/MF/HF name prefixes.
* Keeping both sets would make every item look like two differently-named twins.

Scope and handling (as for the icons before it):
* Kuro Games' assets, downloaded for LOCAL recognition use, stored under the
  gitignored `data/`, not redistributed by this project.
* ONE-TIME setup, explicitly requested. Not runtime egress: the scanner itself
  never makes network calls (AGENTS.md hard constraint 3).
* Requests are serialised with a delay. Do not parallelise this.

Icons from your own zip (D44): the full set is published once as a zip, so a
new install does not scrape the wiki at all; a later plain run then fetches only
items the wiki added since (existing icons are skipped).

    --make-zip [PATH]     pack data/catalogue/ (icons, index, recipes) into a zip
    --from-zip URL|PATH   install from that zip instead of the wiki; a Google Drive
                          share link works as is (shared as "Anyone with the link")

Run:  uv run python tools/fetch_catalogue.py [--from-zip URL] [--make-zip]
"""

from __future__ import annotations

import argparse
import http.client
import io
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from html.parser import HTMLParser
from pathlib import Path

import fetch_pool

API = "https://api.kurobbs.com/wiki/core/catalogue/item/getPage"
OUT = Path("data/catalogue")
INDEX = OUT / "index.json"
#: Wiki category id -> bag tab it feeds. 可合成道具 (craftable dishes/potions)
#: overlaps 补给; entries are de-duplicated by name. 武器 is fetched for the
#: weapons tab, skipped by the scanner for now (D34). 特殊道具 is skipped (D41).
CATEGORIES = {1217: "补给", 1264: "补给", 1161: "资源", 1218: "素材", 1106: "武器"}
DELAY_SECONDS = 0.2
TIMEOUT = 30
ATTEMPTS = 3
#: What a flaky connection raises. IncompleteRead is not a URLError: the wiki
#: dropping one chunked reply mid-body ended the whole run with a traceback.
NETWORK_ERRORS = (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException)
UA = "wuwa-vision/0.1 (local inventory scanner; personal use)"
#: The wiki's own header for the 鸣潮 game (its web client sends the same).
WIKI_TYPE = "9"
#: Where the published zip lives (`--from-zip` with no argument). Set once the zip
#: is uploaded; WUWA_CATALOGUE_ZIP overrides it.
ZIP_URL = os.environ.get("WUWA_CATALOGUE_ZIP", "")


def _request(url: str, data: bytes | None = None) -> bytes:
    headers = {"User-Agent": UA}
    if data is not None:
        headers.update({"Content-Type": "application/x-www-form-urlencoded",
                        "wiki_type": WIKI_TYPE})
    request = urllib.request.Request(url, data=data, headers=headers)
    for attempt in range(1, ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                return response.read()
        except NETWORK_ERRORS:
            if attempt == ATTEMPTS:
                raise
            time.sleep(attempt)  # 1 s, then 2 s: still one request at a time
    raise AssertionError("unreachable")


def fetch_category(catalogue_id: int) -> list[dict]:
    body = urllib.parse.urlencode({"catalogueId": catalogue_id, "page": 1, "limit": 1000})
    payload = json.loads(_request(API, body.encode()))
    if payload.get("code") != 200:
        raise RuntimeError(f"category {catalogue_id}: {payload.get('msg')}")
    return payload["data"]["results"]["records"]


#: Sub-folders of data/catalogue/ that travel in the zip (resonator art, D46).
ZIP_FOLDERS = ("resonators", "avatars", "bosses")


def make_zip(dest: Path) -> int:
    """Pack everything under data/catalogue/ into one zip, for publishing."""
    files = sorted(p for p in OUT.iterdir() if p.is_file())
    for folder in ZIP_FOLDERS:
        if (OUT / folder).is_dir():
            files += sorted(p for p in (OUT / folder).iterdir() if p.is_file())
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(OUT).as_posix())
    print(f"{len(files)} files -> {dest} ({dest.stat().st_size / 1e6:.1f} MB)")
    return 0


_DRIVE_ID = re.compile(r"drive\.google\.com/(?:file/d/|open\?id=|uc\?(?:.*&)?id=)([\w-]+)")


def drive_download_url(url: str) -> str:
    """A Google Drive share link as a direct download; any other URL unchanged.

    Share links (`.../file/d/<id>/view?usp=sharing`, `open?id=<id>`) serve a web
    page, not the file.
    """
    match = _DRIVE_ID.search(url)
    if not match:
        return url
    return f"https://drive.usercontent.google.com/download?id={match.group(1)}&export=download"


class _ConfirmForm(HTMLParser):
    """Drive's "can't scan this file for viruses -- download anyway" form.

    Files over ~25 MB (the catalogue is ~37 MB) get this page instead of the file;
    submitting its form (action + hidden inputs) is the "download anyway" click.
    """

    def __init__(self) -> None:
        super().__init__()
        self.action: str | None = None
        self.fields: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list) -> None:
        a = dict(attrs)
        if tag == "form" and self.action is None and a.get("action"):
            self.action = a["action"]
        elif tag == "input" and a.get("type") == "hidden" and a.get("name"):
            self.fields[a["name"]] = a.get("value") or ""


def download_zip(url: str) -> bytes:
    """The zip at `url`, following Google Drive's download-anyway page if one comes."""
    raw = _request(drive_download_url(url))
    if not zipfile.is_zipfile(io.BytesIO(raw)):
        form = _ConfirmForm()
        form.feed(raw.decode("utf-8", errors="replace"))
        if form.action and form.fields:
            query = urllib.parse.urlencode(form.fields)
            raw = _request(f"{form.action}?{query}")
    if not zipfile.is_zipfile(io.BytesIO(raw)):
        raise SystemExit(
            f"{url} did not return a zip. For Google Drive, share the file as "
            "'Anyone with the link' (Viewer)."
        )
    return raw


def merge_overrides(published: bytes, local: bytes) -> bytes:
    """The zip's hand edits under the user's own: theirs win on the same name."""
    theirs, mine = json.loads(published), json.loads(local)
    merged = {
        "items": {**theirs.get("items", {}), **mine.get("items", {})},
        "weapons": {**theirs.get("weapons", {}), **mine.get("weapons", {})},
    }
    own = list(mine.get("families", []))
    taken = {n for f in own for n in f}
    merged["families"] = [f for f in theirs.get("families", []) if not set(f) & taken] + own
    return json.dumps(merged, ensure_ascii=False, indent=1).encode("utf-8")


def from_zip(source: str) -> int:
    """Install data/catalogue/ from a published zip (URL -- Google Drive too -- or path)."""
    remote = source.startswith(("http://", "https://"))
    raw = download_zip(source) if remote else Path(source).read_bytes()
    OUT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = [n for n in archive.namelist() if not n.endswith("/")]
        for name in names:
            # Never let an entry climb out of data/catalogue/: a bare file name, or
            # one of ZIP_FOLDERS and a bare file name.
            parts = name.replace("\\", "/").split("/")
            folder = parts[0] if len(parts) == 2 and parts[0] in ZIP_FOLDERS else None
            target = OUT / folder / parts[-1] if folder else OUT / parts[-1]
            target.parent.mkdir(parents=True, exist_ok=True)
            data = archive.read(name)
            if target.name == "overrides.json" and target.exists():
                data = merge_overrides(data, target.read_bytes())
            target.write_bytes(data)
    print(f"installed {len(names)} files from {source} -> {OUT}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--make-zip", nargs="?", const="data/catalogue.zip", metavar="PATH")
    parser.add_argument("--from-zip", nargs="?", const=ZIP_URL, metavar="URL_OR_PATH")
    args = parser.parse_args()
    if args.make_zip:
        return make_zip(Path(args.make_zip))
    if args.from_zip is not None:
        if not args.from_zip:
            parser.error("no zip URL set: pass one, or set ZIP_URL / WUWA_CATALOGUE_ZIP")
        return from_zip(args.from_zip)

    OUT.mkdir(parents=True, exist_ok=True)
    entries: dict[str, dict] = {}
    fetched = skipped = failed = 0
    for catalogue_id, tab in CATEGORIES.items():
        try:
            records = fetch_category(catalogue_id)
        except (*NETWORK_ERRORS, RuntimeError, ValueError) as exc:
            # One category down must not cost the others their new items; what
            # this one already has stays in the index (merged below).
            print(f"  FAILED {tab} ({catalogue_id}): {exc}")
            failed += 1
            continue
        print(f"{tab} ({catalogue_id}): {len(records)} entries")
        for record in records:
            content = record.get("content") or {}
            name = (record.get("name") or content.get("title") or "").strip()
            url = content.get("contentUrl")
            if not name or not url or name in entries:
                continue
            star = str(content.get("star") or "")
            entries[name] = {
                "name": name,
                "rarity": int(star) if star.isdigit() else 0,
                "tab": tab,
                "file": f"{record['id']}{Path(urllib.parse.urlparse(url).path).suffix or '.png'}",
                "url": url,
            }
        time.sleep(DELAY_SECONDS)

    todo = []
    for entry in entries.values():
        dest = OUT / entry["file"]
        if dest.exists() and dest.stat().st_size > 0:
            skipped += 1
        else:
            todo.append(entry)

    def download(entry: dict) -> None:
        (OUT / entry["file"]).write_bytes(_request(entry["url"]))

    # a few at a time (D202): the time went on waiting for each answer, not on the bytes
    for done, (entry, _answer, error) in enumerate(
            fetch_pool.each(todo, download, pause=DELAY_SECONDS), skipped + 1):
        if error is None:
            fetched += 1
        elif isinstance(error, NETWORK_ERRORS):
            print(f"  FAILED {entry['name']}: {error}")
            failed += 1
        else:
            raise error
        if done % 100 == 0:
            print(f"  {done}/{len(entries)} ...", flush=True)

    # Keep entries only the zip had (the wiki may have dropped them): merge, not replace.
    previous = json.loads(INDEX.read_text(encoding="utf-8")) if INDEX.exists() else []
    index = [{k: e[k] for k in ("name", "rarity", "tab", "file")} for e in entries.values()]
    index += [e for e in previous if e["name"] not in entries]
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    size = sum(p.stat().st_size for p in OUT.iterdir() if p.suffix != ".json") / 1e6
    print(f"{len(index)} items: fetched={fetched} skipped={skipped} failed={failed} "
          f"({size:.1f} MB) -> {INDEX}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
