# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
# macOS scanner modifications Copyright 2026 leongiscoding (https://github.com/leongiscoding).
"""Window discovery and the window guard on macOS (D71).

The Windows guard (D15) leans on the process name, because a title alone once
matched a browser tab. On macOS the game comes two ways. Kuro's own Mac client
(`WutheringWaves.app`) names itself to the window server as the game, and that
owner is identified exactly as on Windows (D109). Under CrossOver, Parallels or
Whisky the owner is the wrapper, never the game binary, so there the TITLE is the
identifying signal and the owner is shown to the user. Either way, anything that
is not a real, on-screen, normal-layer window is rejected outright.

That is weaker than the Windows guard, and this module says so rather than
pretending otherwise: the honest consequence is that macOS stays passive-only --
`SendInput` has no macOS counterpart here, so nothing can be typed into the wrong
window even if the guard picked one.

Read-only: `CGWindowListCopyWindowInfo` enumerates what the window server already
publishes. It touches no process memory and injects nothing. The frame grab
itself needs Screen Recording permission, which the user grants once in System
Settings. Without it macOS also strips every other app's window TITLE from that
list, so the guard asks for the permission before it looks for the game --
otherwise the refusal says "no game window" while the game sits on screen (D109).

**Untested on hardware**: written without a Mac to run it on. The parts that can
be tested from any desk -- picking the window out of a list, the guard's refusals
-- are, against the window-server dictionaries verbatim.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .windows import GAME_TITLES, WindowGuardError

#: Wrappers the game is known to run under on macOS. Not a security boundary --
#: the title is what identifies the window -- but it is what the user is shown,
#: and an unknown owner is worth saying out loud.
KNOWN_WRAPPERS: tuple[str, ...] = (
    "crossover", "wine", "whisky", "parallels", "vmware", "utm",
)
#: Windows below this size are chrome, not the game (menu bars, tooltips).
MIN_WINDOW = (640, 360)
#: kCGWindowLayer of a normal application window. Anything else is an overlay,
#: a menu or the Dock, and never the game.
NORMAL_LAYER = 0


@dataclass(frozen=True, slots=True)
class MacWindow:
    """One window, as the window server describes it."""

    handle: int
    """kCGWindowNumber -- what the frame grab addresses."""
    title: str
    rect: tuple[int, int, int, int]
    """(left, top, right, bottom) in screen points."""
    process: str
    """kCGWindowOwnerName: the wrapper, not the game."""
    pid: int = 0
    layer: int = 0
    on_screen: bool = True

    @property
    def size(self) -> tuple[int, int]:
        left, top, right, bottom = self.rect
        return (right - left, bottom - top)

    @property
    def label(self) -> str:
        """What to call it in a message: the title, else the app that owns it."""
        return self.title.strip() or self.process

    @property
    def is_native(self) -> bool:
        """Owned by Kuro's own Mac client, which the window server names as the
        game. An exact name, not a substring: "Wuthering Waves Wiki" is a tab."""
        return self.process.strip().lower() in {t.lower() for t in GAME_TITLES}

    @property
    def is_game(self) -> bool:
        return self.is_native or any(t.lower() in self.title.lower() for t in GAME_TITLES)

    @property
    def wrapper(self) -> str | None:
        low = self.process.lower()
        return next((w for w in KNOWN_WRAPPERS if w in low), None)


def from_dicts(entries: list[dict]) -> list[MacWindow]:
    """Turn `CGWindowListCopyWindowInfo` output into windows, largest first.

    Kept separate from the Quartz call so the choosing can be tested with the
    dictionaries verbatim, which is the only part of this file a Windows machine
    can check.
    """
    out = []
    for e in entries:
        bounds = e.get("kCGWindowBounds") or {}
        x, y = int(bounds.get("X", 0)), int(bounds.get("Y", 0))
        w, h = int(bounds.get("Width", 0)), int(bounds.get("Height", 0))
        out.append(MacWindow(
            handle=int(e.get("kCGWindowNumber", 0)),
            title=str(e.get("kCGWindowName") or ""),
            rect=(x, y, x + w, y + h),
            process=str(e.get("kCGWindowOwnerName") or ""),
            pid=int(e.get("kCGWindowOwnerPID", 0) or 0),
            layer=int(e.get("kCGWindowLayer", 0) or 0),
            on_screen=bool(e.get("kCGWindowIsOnscreen", True)),
        ))
    return sorted(out, key=lambda w: -(w.size[0] * w.size[1]))


def game_windows(windows: list[MacWindow]) -> list[MacWindow]:
    """The windows that could be the game: owned or titled like it, normal, big enough."""
    return [
        w for w in windows
        if w.is_game and w.layer == NORMAL_LAYER and w.on_screen
        and w.size[0] >= MIN_WINDOW[0] and w.size[1] >= MIN_WINDOW[1]
    ]


def _window_list() -> list[dict]:
    try:
        from Quartz import CGWindowListCopyWindowInfo as copy_info  # noqa: PLC0415
        from Quartz import (  # noqa: PLC0415
            kCGNullWindowID,
            kCGWindowListExcludeDesktopElements,
            kCGWindowListOptionOnScreenOnly,
        )
    except ImportError as exc:  # pragma: no cover - needs a Mac
        raise WindowGuardError(
            "pyobjc is not installed: uv sync --extra capture-macos"
        ) from exc
    option = kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements
    return list(copy_info(option, kCGNullWindowID) or [])


def list_windows() -> list[MacWindow]:
    """Every on-screen window, largest first."""
    return from_dicts(_window_list())


def frontmost_pid() -> int:
    """The PID of the app in front, or 0 when it cannot be read.

    `NSWorkspace` learns of every app switch from a notification delivered on
    this thread's run loop, and a command-line process never runs one: unpumped,
    the answer is whatever was in front at the first call -- the terminal, so
    `wuwa live` waited out its minute with the game in front (D151). A
    zero-length turn of the run loop delivers what is pending; under a
    millisecond, so the per-frame focus check can afford it. Call it from the
    main thread, as `wuwa live` does: that is the run loop being pumped.
    """
    try:
        from AppKit import NSWorkspace  # noqa: PLC0415
        from Foundation import NSDate, NSRunLoop  # noqa: PLC0415
    except ImportError:  # pragma: no cover - needs a Mac
        return 0
    NSRunLoop.currentRunLoop().runUntilDate_(NSDate.date())
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    return int(app.processIdentifier()) if app is not None else 0


class ScreenRecordingDeniedError(WindowGuardError):
    """This process may not read other apps' windows -- their titles included."""


def screen_recording_allowed() -> bool | None:
    """Whether macOS lets this process record the screen; None if it cannot say."""
    try:
        from Quartz import CGPreflightScreenCaptureAccess  # noqa: PLC0415
    except ImportError:  # pragma: no cover - needs a Mac
        return None
    return bool(CGPreflightScreenCaptureAccess())


def ask_for_screen_recording() -> None:
    """Put the app running this into the Screen Recording list.

    macOS shows its own prompt the first time and does nothing after that, so the
    user finds a switch to turn on rather than an app to go and add.
    """
    try:
        from Quartz import CGRequestScreenCaptureAccess  # noqa: PLC0415
    except ImportError:  # pragma: no cover - needs a Mac
        return
    CGRequestScreenCaptureAccess()


def host_app() -> str:
    """The app macOS grants the permission to: the terminal, never Python.

    An app sets `__CFBundleIdentifier` in what it launches, so VS Code, Cursor,
    iTerm and Terminal all name themselves without a list to keep up to date.
    """
    bundle = os.environ.get("__CFBundleIdentifier", "")  # noqa: SIM112 - macOS spells it so
    if bundle:
        try:
            from AppKit import NSWorkspace  # noqa: PLC0415

            url = NSWorkspace.sharedWorkspace().URLForApplicationWithBundleIdentifier_(bundle)
        except ImportError:  # pragma: no cover - needs a Mac
            url = None
        if url is not None:
            return Path(str(url.path())).stem
    return "the app you run wuwa from"


def screen_recording_hint() -> str:
    """What to switch on, where, and the restart nobody guesses."""
    app = host_app()
    return (
        f"allow Screen Recording for {app} in System Settings > Privacy & Security > "
        f"Screen & System Audio Recording, then run this again (quit and reopen {app} "
        "if it still refuses)"
    )


def require_window(must_be_foreground: bool = True) -> MacWindow:
    """The game window, or refuse with the reason. Fails closed (D15).

    The permission comes first: without it macOS hands over the window list with
    every title blanked, and "no game window" would be the wrong refusal (D109).
    """
    if screen_recording_allowed() is False:
        ask_for_screen_recording()
        raise ScreenRecordingDeniedError(
            "macOS hides other apps' windows until Screen Recording is allowed: "
            + screen_recording_hint()
        )
    found = game_windows(list_windows())
    if not found:
        raise WindowGuardError(
            "no window titled like the game is open "
            f"(looking for {', '.join(GAME_TITLES)})"
        )
    window = found[0]
    if must_be_foreground and not is_game_foreground(window):
        raise WindowGuardError(f"{window.label} is not the front window")
    return window


def is_game_foreground(window: MacWindow) -> bool:
    """True only while that very window's app is the front one."""
    pid = frontmost_pid()
    return bool(pid) and pid == window.pid


def wait_for_foreground(
    *,
    timeout: float = 60.0,
    on_wait: Callable[[float], None] | None = None,
    should_abort: Callable[[], bool] | None = None,
    poll: float = 0.5,
    probe: Callable[[], MacWindow] | None = None,
    front: Callable[[MacWindow], bool] | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> MacWindow:
    """Hold until the game is in front, reading nothing meanwhile (D15).

    The Windows guard's contract exactly (D90): `on_wait` gets the seconds left,
    `should_abort` lets the panic key end the wait, and a missing window is
    retried until the deadline rather than refused on the first look.
    """
    find = probe or (lambda: require_window(must_be_foreground=False))
    in_front = front or is_game_foreground
    deadline = clock() + timeout
    reason = "the game window never came to the front"
    while True:
        if should_abort is not None and should_abort():
            raise WindowGuardError("aborted while waiting for the game window")
        try:
            window = find()
            if in_front(window):
                return window
            reason = f"{window.label} is open but not the front window"
        except ScreenRecordingDeniedError:
            raise  # waiting cannot fix it: someone has to flip the switch
        except WindowGuardError as exc:
            reason = str(exc)
        remaining = deadline - clock()
        if remaining <= 0:
            raise WindowGuardError(f"waited {timeout:.0f}s -- {reason}")
        if on_wait is not None:
            on_wait(remaining)
        sleep(min(poll, remaining))
