# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Frame-stability gating for passive scanning (PLAN.md D14).

In passive mode the user scrolls and the tool decides, on its own, when a frame is
worth reading. Two things must be true before a frame is processed:

1. **Settled.** The grid must have stopped moving. WuWa's bag scrolls with inertia,
   so mid-scroll frames are smeared and land on arbitrary sub-row offsets.
2. **New.** It must differ from the last frame we already processed, or a user
   sitting still would re-read the same page dozens of times per second.

Gating is on **inter-frame difference**, never a per-frame quality score. Measured
Laplacian variance across the fixtures spans 1639-4409 purely from *content* --
flower tiles carry far less edge energy than crystal tiles -- so no absolute
sharpness threshold can separate "blurred by scrolling" from "soft artwork".

No input hooks are used. Watching pixels is the whole mechanism, which is what
keeps passive mode's footprint at zero (D1/D6).
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field

import cv2
import numpy as np

from .base import Frame

#: Fractional (left, top, right, bottom) window over the grid.
DEFAULT_ROI = (0.06, 0.08, 0.74, 0.90)
#: Signature resolution. Small enough to be cheap, large enough that a one-row
#: scroll moves it well clear of sensor noise.
SIGNATURE_SIZE = (64, 48)
#: Mean absolute difference below which two frames count as identical.
STILL_THRESHOLD = 1.0
#: Consecutive still frames required before a frame is accepted.
STABLE_FRAMES = 3
#: Live only (D97). Three still frames is ~30 ms at this capture rate, and the bag
#: opening eases to a stop slowly enough that each frame is within STILL_THRESHOLD
#: of the one before: a view was read mid-animation, 8 washed-out tiles at 85% of
#: their size. So motion is measured against the frame from this long ago, not
#: the previous one, and the screen must hold still this long before it is read.
MOTION_WINDOW = 0.10
MIN_STILL_SECONDS = 0.30
#: A settled frame must differ from the last ACCEPTED one by at least this much.
#: 6.0, not 2.0: live, the bag's animated background alone scored 2.0-3.1 with
#: nothing touched, so every view was re-read (~8 s each) in a loop; a scroll
#: scores 17+. A click (3.9) is no longer caught here -- the scan loop probes for
#: a moved selection outline instead (D39).
NOVELTY_THRESHOLD = 6.0


def signature(frame: Frame, roi: tuple[float, float, float, float] = DEFAULT_ROI) -> np.ndarray:
    """Cheap, shift-sensitive fingerprint of the grid region.

    Order matters for speed: slice, then DOWNSAMPLE, then convert to grey. Greying
    the full-resolution ROI first costs ~50 ms per frame on a 3439x1439 capture,
    which would cap the capture loop below its target rate. Downsampling first
    drops that by roughly two orders of magnitude, and INTER_AREA is itself the
    block mean we want.
    """
    rgb = frame.rgb
    h, w = rgb.shape[:2]
    x0, y0 = int(w * roi[0]), int(h * roi[1])
    x1, y1 = int(w * roi[2]), int(h * roi[3])
    region = rgb[y0:y1, x0:x1]
    if region.size == 0:
        region = rgb
    small = cv2.resize(region, SIGNATURE_SIZE, interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(small, cv2.COLOR_RGB2GRAY).astype(np.float32)


def difference(a: np.ndarray, b: np.ndarray) -> float:
    if a.shape != b.shape:
        return float("inf")
    return float(np.abs(a - b).mean())


@dataclass
class GateStats:
    seen: int = 0
    accepted: int = 0
    moving: int = 0
    """Rejected because the grid was still changing."""
    repeat: int = 0
    """Rejected because it matched the last accepted frame."""
    settling: int = 0
    """Still frames counted toward the stability run but not yet accepted."""

    def as_dict(self) -> dict[str, int]:
        return {
            "seen": self.seen,
            "accepted": self.accepted,
            "moving": self.moving,
            "repeat": self.repeat,
            "settling": self.settling,
        }


@dataclass
class FrameGate:
    """Decides which frames are worth reading.

    Feed every captured frame to `offer`; it returns the frame when it should be
    processed, or None to skip it.
    """

    roi: tuple[float, float, float, float] = DEFAULT_ROI
    still_threshold: float = STILL_THRESHOLD
    stable_frames: int = STABLE_FRAMES
    novelty_threshold: float = NOVELTY_THRESHOLD
    motion_window: float = 0.0
    """Seconds back to compare each frame against; 0 = the previous frame, which
    is what a fixture replay wants (its frames have no real time between them)."""
    min_still_seconds: float = 0.0
    """How long the screen must have been still before a frame is accepted."""
    clock: Callable[[], float] = time.monotonic
    stats: GateStats = field(default_factory=GateStats)

    _previous: np.ndarray | None = field(default=None, repr=False)
    _accepted: np.ndarray | None = field(default=None, repr=False)
    _still_run: int = field(default=0, repr=False)
    _recent: deque = field(default_factory=deque, repr=False)
    _still_since: float | None = field(default=None, repr=False)
    last_novelty: float = 0.0
    """How far the last settled frame was from the last accepted one (diagnostics)."""
    moved_at: float | None = None
    """time.monotonic() of the last frame that was still moving (diagnostics)."""

    def reset(self) -> None:
        """Make the grid re-settle (after a focus change).

        The last ACCEPTED signature is kept: coming back to an unchanged page must
        not re-read it. Live, every alt-tab to the live page produced another
        '+0 new' view and ~2 s of OCR the user had to wait out.
        """
        self._previous = None
        self._still_run = 0
        self._recent.clear()
        self._still_since = None

    @classmethod
    def live(cls, **kwargs: object) -> FrameGate:
        """The gate for a real screen: stillness is measured in time, not frames."""
        return cls(motion_window=MOTION_WINDOW, min_still_seconds=MIN_STILL_SECONDS, **kwargs)

    def accept(self, frame: Frame) -> None:
        """Record `frame` as read although `offer` did not pass it (a click view).

        Without this the next settled frame is compared with the view BEFORE the
        click; the new outline and panel then read as a scroll (novelty 20.6
        live) and the same page was read twice (D39).
        """
        self._accepted = signature(frame, self.roi)

    def offer(self, frame: Frame) -> Frame | None:
        self.stats.seen += 1
        current = signature(frame, self.roi)

        if self._previous is None:
            self._previous = current
            self._still_run = 1
            self._still_since = self.clock()
            if self.motion_window > 0:
                self._recent.append((self._still_since, current))
            self.stats.settling += 1
            return None

        now = self.clock()
        reference = self._previous
        if self.motion_window > 0:
            # The oldest frame still inside the window: a slow ease that moves
            # under the threshold per frame does not move under it per 100 ms.
            while self._recent and now - self._recent[0][0] > self.motion_window:
                self._recent.popleft()
            if self._recent:
                reference = self._recent[0][1]
            self._recent.append((now, current))
        moved = difference(current, reference)
        self._previous = current

        if moved > self.still_threshold:
            self._still_run = 0
            self._still_since = None
            self.moved_at = time.monotonic()
            self.stats.moving += 1
            return None

        self._still_run += 1
        if self._still_since is None:
            self._still_since = now
        if (self._still_run < self.stable_frames
                or now - self._still_since < self.min_still_seconds):
            self.stats.settling += 1
            return None

        self.last_novelty = (
            difference(current, self._accepted) if self._accepted is not None else float("inf")
        )
        if self.last_novelty < self.novelty_threshold:
            self.stats.repeat += 1
            return None

        self._accepted = current
        self.stats.accepted += 1
        return frame
