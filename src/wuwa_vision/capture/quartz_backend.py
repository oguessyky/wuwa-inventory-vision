# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
# macOS scanner modifications Copyright 2026 leongiscoding (https://github.com/leongiscoding).
"""Live capture on macOS (D71).

Frames come from the window server's own copy of the window
(`CGWindowListCreateImage`), the same read-only path a screenshot takes: **no
game-process interaction, no hooks, no injection**, exactly like WGC on Windows.
It needs Screen Recording permission, granted once in System Settings; without it
the call returns an empty image, which this reports as such instead of yielding
black frames.

Unlike WGC, nothing pushes frames at us, so this polls at `fps` on its own thread
and keeps only the newest -- the same drop-oldest buffer, because the scanner
wants the current screen and D14 gates on inter-frame difference anyway.

The grabber is injected (`grab=`), so the buffer, the gating and the shutdown can
be tested on any machine; only the Quartz call itself needs a Mac.

**Untested on hardware.**
"""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Callable, Iterator

import numpy as np

from .base import Frame
from .macos import MacWindow, require_window, screen_recording_hint

#: Polling rate. The bag is a still picture between scrolls, and the frame gate
#: throws away repeats anyway, so there is nothing to win above this.
DEFAULT_FPS = 10.0


class CaptureUnavailableError(RuntimeError):
    """Nothing can be captured -- usually Screen Recording permission."""


def _cg_grab(window_id: int) -> np.ndarray | None:  # pragma: no cover - needs a Mac
    """One RGB frame of that window from the window server, or None."""
    from Quartz import CGDataProviderCopyData as copy_data
    from Quartz import (
        CGImageGetBytesPerRow,
        CGImageGetDataProvider,
        CGImageGetHeight,
        CGImageGetWidth,
        CGRectNull,
        kCGWindowImageBoundsIgnoreFraming,
        kCGWindowListOptionIncludingWindow,
    )
    from Quartz import CGWindowListCreateImage as create_image

    image = create_image(
        CGRectNull, kCGWindowListOptionIncludingWindow, window_id,
        kCGWindowImageBoundsIgnoreFraming,
    )
    if image is None:
        return None
    width, height = CGImageGetWidth(image), CGImageGetHeight(image)
    if not width or not height:
        return None
    stride = CGImageGetBytesPerRow(image)
    raw = copy_data(CGImageGetDataProvider(image))
    buffer = np.frombuffer(bytes(raw), dtype=np.uint8)
    # BGRA rows are padded to `stride`; the padding is not pixels.
    rows = buffer[: stride * height].reshape(height, stride // 4, 4)
    return np.ascontiguousarray(rows[:, :width, [2, 1, 0]])


class QuartzCapture:
    """Frames from one window, newest first, dropping stale ones."""

    def __init__(
        self,
        window: MacWindow | None = None,
        *,
        fps: float = DEFAULT_FPS,
        grab: Callable[[int], np.ndarray | None] | None = None,
        blank_limit: int | None = None,
    ) -> None:
        self.window = window or require_window()
        self.fps = fps
        #: Empty grabs in a row before this is called a permission problem
        #: rather than a slow frame -- about three seconds' worth.
        self.blank_limit = blank_limit or max(int(fps * 3), 5)
        self._grab = grab or _cg_grab
        self._buffer: deque[np.ndarray] = deque(maxlen=1)
        self._arrived = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._seq = 0
        self._blank = 0

    # ------------------------------------------------------------- lifecycle

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._pump, name="quartz-capture", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=2.0)

    def _pump(self) -> None:
        period = 1.0 / max(self.fps, 1.0)
        while not self._stop.is_set():
            frame = self._grab(self.window.handle)
            if frame is None or not frame.size:
                self._blank += 1
            else:
                self._blank = 0
                self._buffer.append(frame)
                self._arrived.set()
            self._stop.wait(period)

    # ---------------------------------------------------------------- frames

    def frames(self, timeout: float | None = None) -> Iterator[Frame]:
        """Yield the newest frame as it arrives, until `stop()` or `timeout`.

        A run of empty grabs is a permission problem, not a slow frame: say so
        once rather than feeding the pipeline black pictures.
        """
        self.start()
        waited = 0.0
        step = 1.0 / max(self.fps, 1.0)
        while not self._stop.is_set():
            if self._blank >= self.blank_limit:
                raise CaptureUnavailableError(
                    f"the window server returned nothing: {screen_recording_hint()}"
                )
            if self._buffer:
                self._seq += 1
                yield Frame(rgb=self._buffer[-1], source=self.window.title, seq=self._seq)
                waited = 0.0
            else:
                waited += step
                if timeout is not None and waited >= timeout:
                    return
            self._stop.wait(step)

    def __enter__(self) -> QuartzCapture:
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()
