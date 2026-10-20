# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Curate redacted regression fixtures from raw captures.

Raw captures in train_dataset/ are gitignored: they carry the player UID
(bottom-right watermark) and, on co-op frames, friend portraits + display names.
This produces a small redacted subset that IS safe to track.

Run:  uv run python tools/make_fixtures.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageFilter

RAW = Path("train_dataset/train_dataset")
OUT = Path("tests/fixtures")

# Fractional boxes, so the same rule works at 3439x1439, 3437x1437 and 2940x1912.
UID_BOX = (0.880, 0.955, 1.000, 1.000)      # 特征码 watermark, bottom-right
COOP_BOX = (0.004, 0.320, 0.0700, 0.450)    # co-op portraits + display names, left edge

# source stem -> fixture name. Redaction is UNCONDITIONAL: co-op overlays turned up
# on frames we had not flagged, and a per-file flag is a PII bug waiting to happen.
SELECTION = [
    ("wuwa_inventory_system_21", "res_21_9_a"),
    ("wuwa_inventory_system_23", "res_21_9_b"),
    ("wuwa_inventory_system_24", "res_21_9_c"),
    ("wuwa_inventory_system_19", "res_21_9_rgba"),
    ("wuwa_inventory_system_3", "res_3_2_6col_a"),
    ("wuwa_inventory_system_4", "res_3_2_6col_b"),
    ("wuwa_inventory_system_30", "mat_top_selected"),
    ("wuwa_inventory_system_31", "mat_flowers_nobar"),
    ("wuwa_inventory_system_32", "mat_scrolled_a"),
    ("wuwa_inventory_system_33", "mat_scrolled_b"),
    # The 武器 tab (D61): its tiles carry a level, a holder portrait and a count
    # in a place of their own. _1 is a page of finished 5-star weapons, _2 holds
    # the weapon EXP material, which is an ordinary bag tile in that tab, and _3
    # runs from level 1 to 70.
    ("wuwa_weapon_1", "wpn_equipped"),
    ("wuwa_weapon_2", "wpn_materials"),
    ("wuwa_weapon_3", "wpn_levels"),
]


def _px(box: tuple[float, float, float, float], w: int, h: int) -> tuple[int, int, int, int]:
    left, top, right, bottom = box
    return (int(left * w), int(top * h), int(right * w), int(bottom * h))


def _fill_median(im: Image.Image, box: tuple[int, int, int, int]) -> None:
    """Flatten a region to its own median colour. No hard edge, text destroyed."""
    region = im.crop(box)
    med = region.resize((1, 1), Image.Resampling.BOX).getpixel((0, 0))
    im.paste(Image.new("RGB", (box[2] - box[0], box[3] - box[1]), med), box)


def _pixelate(im: Image.Image, box: tuple[int, int, int, int], block: int = 22) -> None:
    """Mosaic + blur. Preserves local statistics, so it won't fake an edge near the grid."""
    region = im.crop(box)
    w, h = region.size
    small = region.resize((max(1, w // block), max(1, h // block)), Image.Resampling.BOX)
    mosaic = small.resize((w, h), Image.Resampling.NEAREST)
    im.paste(mosaic.filter(ImageFilter.GaussianBlur(3)), box)


def _find(stem: str) -> Path | None:
    for cand in (RAW / stem, RAW / f"{stem}.png"):
        if cand.exists():
            return cand
    return None


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    total = 0
    for stem, name in SELECTION:
        src = _find(stem)
        if src is None:
            print(f"  MISSING {stem}", file=sys.stderr)
            return 1
        im = Image.open(src).convert("RGB")
        w, h = im.size
        _fill_median(im, _px(UID_BOX, w, h))
        _pixelate(im, _px(COOP_BOX, w, h))
        dst = OUT / f"{name}.webp"
        im.save(dst, "WEBP", lossless=True, quality=100, method=4)
        size = dst.stat().st_size
        total += size
        print(f"  {name:<20} {w}x{h}  {size / 1e6:5.2f} MB  (from {src.name})")
    print(f"total: {total / 1e6:.1f} MB across {len(SELECTION)} fixtures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
