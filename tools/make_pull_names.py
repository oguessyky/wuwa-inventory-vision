# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Put the pulls named by hand on this machine into the file the app ships (D135).

A pull export names each pull by the game's id and by an English name. Kuro's
wiki has neither for a weapon, and nothing else is asked, so the only way the
app comes to know that 21010012 "Tyro Broadblade" is 原初长刃·朴石 is that
somebody says so, once, on the 更新 page. That lands in
data/catalogue/overrides.json ("gids", "pull_english"), which is this machine's
own. This tool copies it into assets/pull_names.json, which is committed and
ships: everyone else's import then places those pulls by id, or by the English
name alone, without being asked.

It only ever adds what was named by hand here. Entries already in the file are
kept; one named again here is replaced. Nothing is downloaded.

Run:  uv run python tools/make_pull_names.py [--check]
      --check   say what would be added and change nothing
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wuwa_vision.catalogue import (  # noqa: E402
    PULL_NAMES,
    read_game_english,
    read_overrides,
    read_pull_names,
)

ABOUT = ("Names for placing pulls (PLAN.md D135, D147). 'weapons' and 'resonators': pulls named "
         "by hand -- the game's id, its name in the catalogue, and the English name a pull export "
         "gives it -- written by tools/make_pull_names.py from names given on the 更新 page. "
         "'english': for the weapons nobody has pulled and named yet, the name in the catalogue "
         "and the game's own English name for it, with no id, so that a pull is placed by its "
         "name alone. The app fetches nothing of this from anywhere.")


def merge(shipped: dict, overrides: dict) -> tuple[dict, list[str]]:
    """The shipped names with this machine's hand-given ones folded in, and what changed."""
    out = {kind: dict(entries) for kind, entries in shipped.items()}
    changed: list[str] = []
    english = overrides.get("pull_english") or {}
    for gid, name in sorted((overrides.get("gids") or {}).items()):
        gid = str(gid)
        kind = "weapons" if len(gid) >= 8 else "resonators"
        entry = {"name": name, **({"english": english[gid]} if english.get(gid) else {})}
        if out[kind].get(gid) != entry:
            out[kind][gid] = entry
            said = f"  ({entry['english']})" if "english" in entry else ""
            changed.append(f"{gid}  {name}{said}")
    return out, changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="say what would change; write nothing")
    args = parser.parse_args()
    # the names are Chinese, and a Windows console is not always able to say them
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    merged, changed = merge(read_pull_names(), read_overrides())
    for line in changed:
        print("+", line)
    total = sum(len(v) for v in merged.values())
    if args.check or not changed:
        print(f"{len(changed)} to add; {total} in all" + ("" if changed else " -- nothing to do"))
        return 0
    # "english" is not this tool's to make: the names with no id are kept as they are
    data = {"about": ABOUT, "english": read_game_english(),
            **{kind: dict(sorted(entries.items())) for kind, entries in merged.items()}}
    PULL_NAMES.parent.mkdir(parents=True, exist_ok=True)
    PULL_NAMES.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"added {len(changed)}; {total} in all -> {PULL_NAMES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
