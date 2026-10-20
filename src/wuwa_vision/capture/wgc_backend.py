# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Live capture via Windows Graphics Capture (PLAN.md D4).

WGC is the same OS compositor API OBS uses internally: **zero game-process
interaction, no hooks, no injection**, and lossless BGRA. OBS Virtual Camera was
rejected because its NV12 4:2:0 output corrupts the rarity-bar colour that the
rarity classifier keys on.

The window is addressed by **HWND, not title**. That matters: title matching alone
once selected a browser tab named "Items | Wuthering Waves Resource & Companion
App". The handle comes from `windows.require_window()`, which verifies the owning
process, so capture can only ever target a window the guard approved.

`windows-capture` delivers frames through a callback on its own thread. This wraps
that in a drop-oldest buffer: a scanner wants the most recent frame, never a
backlog, and D14 gates on inter-frame difference anyway.
"""

from __future__ import annotations

import contextlib
import threading
from collections import deque
from collections.abc import Iterator
from typing import Any

import numpy as np

from .base import Frame
from .windows import WindowInfo, require_window


class WgcCapture:
    """Frames from one window, newest-first, dropping stale frames."""

    def __init__(self, window: WindowInfo | None = None, *, cursor: bool = False) -> None:
        self.window = window or require_window()
        self.cursor = cursor
        self._buffer: deque[np.ndarray] = deque(maxlen=1)
        self._arrived = threading.Event()
        self._control: Any = None
        self._closed = threading.Event()
        self._seq = 0

    def start(self) -> None:
        from windows_capture import WindowsCapture

        capture = WindowsCapture(
            cursor_capture=self.cursor,
            draw_border=False,
            window_hwnd=self.window.handle,
        )

        @capture.event
        def on_frame_arrived(frame: Any, capture_control: Any) -> None:  # noqa: ARG001
            rgb = _to_rgb(frame)
            if rgb is not None:
                self._buffer.append(rgb)
                self._arrived.set()

        @capture.event
        def on_closed() -> None:
            self._closed.set()
            self._arrived.set()

        self._control = capture.start_free_threaded()

    def stop(self) -> None:
        if self._control is not None:
            with contextlib.suppress(Exception):
                self._control.stop()
            self._control = None

    def grab(self, timeout: float = 5.0) -> Frame | None:
        """Wait for the next frame. Returns None on timeout or if capture closed."""
        self._arrived.clear()
        if not self._buffer and not self._arrived.wait(timeout):
            return None
        if self._closed.is_set() and not self._buffer:
            return None
        if not self._buffer:
            return None
        rgb = self._buffer[-1]
        self._seq += 1
        return Frame(rgb=rgb, source=self.window.title, seq=self._seq)

    def frames(self, limit: int | None = None, timeout: float = 5.0) -> Iterator[Frame]:
        if self._control is None:
            self.start()
        produced = 0
        while limit is None or produced < limit:
            frame = self.grab(timeout)
            if frame is None:
                return
            produced += 1
            yield frame

    def __enter__(self) -> WgcCapture:
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()


def _to_rgb(frame: Any) -> np.ndarray | None:
    """Normalise a library frame to an (H, W, 3) uint8 RGB array.

    The buffer is BGRA; the attribute name has moved between versions, so probe
    rather than assume.
    """
    buffer = None
    for attribute in ("frame_buffer", "buffer", "data"):
        buffer = getattr(frame, attribute, None)
        if buffer is not None:
            break
    if buffer is None:
        try:
            buffer = np.asarray(frame)
        except Exception:
            return None

    array = np.asarray(buffer)
    if array.ndim != 3 or array.shape[2] < 3:
        return None
    # BGRA -> RGB
    return np.ascontiguousarray(array[:, :, 2::-1])
