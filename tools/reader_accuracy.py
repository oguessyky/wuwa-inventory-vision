# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""How well 计算's reader reads passives it has never seen (D317), on the catalogue here.

Every passive read by hand is held out in turn with its group -- a weapon, a set, a main echo, one
resonator's buffs all together, as a new resonator comes -- and read as new: by the reader alone,
and by the reader taught by the readings of the rest (`calc_learn`). Prints, by kind, how many were
read exactly as by hand and the effects' precision and recall; "corrected" is the items the reader
alone gets wrong. Nothing is written.

    uv run python tools/reader_accuracy.py [--folds 5]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wuwa_vision import calc_data, calc_learn  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--folds", type=int, default=5)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    raw = json.loads((ROOT / "data" / "catalogue" / calc_data.NAME).read_text(encoding="utf-8"))
    found = calc_learn.items(raw, calc_data.JUDGED)
    report = calc_learn.holdout(found, folds=args.folds)
    print(f"{len(found)} passives read by hand, held out in {args.folds} folds by group")
    print(f"{'':10} {'items':>6}  {'reader exact':>13} {'P':>6} {'R':>6}   "
          f"{'taught exact':>13} {'P':>6} {'R':>6}")
    for kind in ("weapon", "set", "echo", "role", "all", "corrected"):
        a, b = report["reader"].get(kind), report["learned"].get(kind)
        if not a:
            continue
        n = a["items"]
        print(f"{kind:10} {n:>6}  {a['exact']:>5} {a['exact'] / n:>6.1%} {a['precision']:>6.1%} "
              f"{a['recall']:>6.1%}   {b['exact']:>5} {b['exact'] / n:>6.1%} "
              f"{b['precision']:>6.1%} {b['recall']:>6.1%}")
    print("read as:", report["how"])


if __name__ == "__main__":
    main()
