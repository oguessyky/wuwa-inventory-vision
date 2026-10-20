# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""A small colour thumbnail of an icon, for cheap same-item comparisons.

DINOv2 embeddings are nearly colour-blind: the element variants of one potion
(湮灭 / 衍射 / ... 干涉混悬液 -- same art, different colour) embed as near
neighbours, so a name learned for one spread to all of them (D30). This vector
keeps colour. Two crops of the same item from the game screen score >= 0.995;
colour variants of one design scored 0.78-0.91.
"""

from __future__ import annotations

import cv2
import numpy as np

from .masking import apply_badge_mask


def describe(icon: np.ndarray) -> np.ndarray:
    """A 16x16 colour thumbnail, zero-mean and unit-norm, for cosine comparison.

    Badges are masked and the border trimmed so the selection outline and the
    `新` / `+` corners -- which come and go between frames -- do not count.
    """
    icon = apply_badge_mask(icon)
    h, w = icon.shape[:2]
    core = icon[int(h * 0.08) : int(h * 0.92), int(w * 0.08) : int(w * 0.92)]
    vec = cv2.resize(core, (16, 16), interpolation=cv2.INTER_AREA).astype(np.float32).ravel()
    vec -= vec.mean()
    return vec / (float(np.linalg.norm(vec)) + 1e-6)


#: Hue bins of the signature (OpenCV hue is 0-179).
HUE_BINS = 24
#: Below this much vivid colour (weighted pixel fraction) an icon is effectively
#: colourless -- white rice, grey metal -- and hue says nothing about it.
MIN_HUE_MASS = 0.002


def hue_signature(icon: np.ndarray) -> np.ndarray:
    """Histogram of hue over the vivid pixels, per pixel of the crop.

    `describe` compares shape and brightness as much as colour, so a red and a
    yellow potion of one design still scored >= 0.95 on it. This keeps only hue:
    pixels are weighted by how saturated and bright they are, so white bodies,
    dark backgrounds and grey metal contribute nothing (D30).
    """
    icon = apply_badge_mask(icon)
    h, w = icon.shape[:2]
    core = icon[int(h * 0.08) : int(h * 0.92), int(w * 0.08) : int(w * 0.92)]
    hsv = cv2.cvtColor(np.ascontiguousarray(core), cv2.COLOR_RGB2HSV)
    hue = hsv[..., 0].astype(np.int32)
    sat = hsv[..., 1].astype(np.float32) / 255.0
    val = hsv[..., 2].astype(np.float32) / 255.0
    weight = np.clip(sat - 0.35, 0, None) * np.clip(val - 0.30, 0, None)
    hist = np.bincount(
        (hue * HUE_BINS // 180).ravel(), weights=weight.ravel(), minlength=HUE_BINS
    )[:HUE_BINS]
    return (hist / max(hue.size, 1)).astype(np.float32)


def same_hue(a: np.ndarray, b: np.ndarray, threshold: float) -> bool:
    """True unless both icons are clearly coloured and their hues differ.

    Measured on a live 补给 scan: the same item across views scored >= 0.946
    (99% >= 0.99); colour variants of one design scored 0.0-0.2.
    """
    if min(float(a.sum()), float(b.sum())) < MIN_HUE_MASS:
        return True
    cos = float(a @ b) / (float(np.linalg.norm(a) * np.linalg.norm(b)) + 1e-12)
    return cos >= threshold
