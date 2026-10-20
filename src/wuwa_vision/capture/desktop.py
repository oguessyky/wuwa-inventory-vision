# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""The desktop this build is running on (D71).

`cli` asks for "the window guard" and "live capture" and gets whichever
implementation this machine has: Windows Graphics Capture on Windows, the window
server on macOS. Nothing above this line knows which one it is holding, which is
the same rule the file/live split already follows (D4).

It asks for "the scan plan" the same way (D152): what reads the frames, how the
game is found, what puts it in front and what stops a scan, said once per OS.
The Mac was told to alt-tab and to press F9 until then -- and F9 stops nothing
there; Ctrl+C does.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..safety.panic import DEFAULT_KEY, MAC_KEY
from .windows import GAME_PROCESSES, GAME_TITLES, WindowGuardError

MACOS = sys.platform == "darwin"
WINDOWS = sys.platform == "win32"

__all__ = [
    "MACOS",
    "WINDOWS",
    "ScanPlan",
    "WindowGuardError",
    "is_game_foreground",
    "list_windows",
    "live_capture",
    "require_window",
    "scan_plan",
    "wait_for_foreground",
]


@dataclass(frozen=True, slots=True)
class ScanPlan:
    """How `wuwa live` runs on one OS. Words for the user, not switches: the
    implementations are still picked by `_guard` and `live_capture` below."""

    system: str
    """The OS, as a message names it."""
    supported: bool
    """Whether `wuwa live` runs here at all. `wuwa scan` reads saved frames anywhere."""
    frames: str
    """What hands over the game's pictures."""
    finds_game: str
    """How the game window is told apart from every other window."""
    to_front: str
    """What the user does to put the game in front; reads as "waits for you to ..."."""
    stop: str
    """What ends a scan, before any --panic-key."""
    permission: str | None = None
    """What the OS must allow first, if anything."""
    front_note: str | None = None
    """The mistake worth heading off while the guard waits."""


def scan_plan(platform: str = sys.platform) -> ScanPlan:
    """The plan for this machine -- or for `platform`, which is how it is tested."""
    if platform == "darwin":
        return ScanPlan(
            system="macOS",
            supported=True,
            frames="the window server's copy of the game window (Quartz, 10 fps)",
            finds_game=(
                "a window owned by the game itself (Kuro's Mac client), else one titled "
                f"{' / '.join(GAME_TITLES)} (CrossOver, Parallels, Whisky)"
            ),
            to_front="click into the game window (or Cmd-Tab to it)",
            stop=MAC_KEY,
            permission="Screen Recording, for the app you run wuwa from",
            front_note="pointing the mouse at the game is not enough: macOS focuses on a click",
        )
    if platform == "win32":
        return ScanPlan(
            system="Windows",
            supported=True,
            frames="Windows Graphics Capture of the game window",
            finds_game=f"a window owned by {' / '.join(GAME_PROCESSES)}",
            to_front="alt-tab into the game",
            stop=f"{DEFAULT_KEY}, a global hotkey (--panic-key to change it)",
        )
    name = "Linux" if platform.startswith("linux") else platform
    return ScanPlan(
        system=name,
        supported=False,
        frames="none: live scanning runs on Windows and macOS only",
        finds_game="-",
        to_front="-",
        stop="-",
    )


def _guard() -> Any:
    if MACOS:
        from . import macos

        return macos
    from . import windows

    return windows


def list_windows() -> list[Any]:
    return _guard().list_windows()


def require_window(must_be_foreground: bool = True) -> Any:
    return _guard().require_window(must_be_foreground=must_be_foreground)


def is_game_foreground(window: Any) -> bool:
    return _guard().is_game_foreground(window)


def wait_for_foreground(
    *,
    timeout: float = 60.0,
    on_wait: Callable[[float], None] | None = None,
    should_abort: Callable[[], bool] | None = None,
) -> Any:
    """Hold until the game is in front -- one contract on both desktops (D90).

    `on_wait` gets the seconds left, for the countdown; `should_abort` is how the
    panic key gets a say while waiting. This wrapper once took different names
    from the Windows guard it forwards to, and `wuwa live` crashed on Windows the
    moment it reached the wait.
    """
    return _guard().wait_for_foreground(timeout=timeout, on_wait=on_wait,
                                        should_abort=should_abort)


def live_capture(window: Any) -> Any:
    """The live capture backend for this machine."""
    if MACOS:
        from .quartz_backend import QuartzCapture

        return QuartzCapture(window=window)
    from .wgc_backend import WgcCapture

    return WgcCapture(window=window)
