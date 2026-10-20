# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Capture backend interface.

Two implementations are interchangeable by design (PLAN.md D4/D18):
  * `FileCapture`  - replays fixture frames, so the whole pipeline is testable
                     with the game not running.
  * `WgcCapture`   - Windows Graphics Capture, live. Milestone 2.

Nothing downstream may know which one it is holding.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np


@dataclass(frozen=True, slots=True)
class Frame:
    """One captured frame."""

    rgb: np.ndarray
    """(H, W, 3) uint8."""
    source: str
    """Where it came from -- a fixture name or a window title."""
    seq: int = 0

    @property
    def size(self) -> tuple[int, int]:
        h, w = self.rgb.shape[:2]
        return (w, h)

    def grey(self) -> np.ndarray:
        """Luma, float32. Rec. 601 weights."""
        r, g, b = self.rgb[..., 0], self.rgb[..., 1], self.rgb[..., 2]
        return (0.299 * r + 0.587 * g + 0.114 * b).astype(np.float32)


@runtime_checkable
class CaptureBackend(Protocol):
    """Source of frames."""

    def frames(self) -> list[Frame] | object:
        """Yield frames. Live backends are unbounded; file backends terminate."""
        ...
