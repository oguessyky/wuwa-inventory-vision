# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Window discovery and the window guard.

The guard is a hard safety requirement (PLAN.md D15): nothing may capture or
synthesise input unless the expected game window is present AND foreground. The
scan fails closed when it is not -- shrugging off a lost window is how a tool ends
up acting on whatever surface happens to be underneath.

The guard is a *precondition*, not a launch-time veto. A command started from a
terminal can never satisfy it at the instant it starts -- the terminal is the
foreground window -- so `wait_for_foreground` lets the caller hold, refusing to
capture the whole time, until the user alt-tabs into the game. Waiting is not a
weakening: no frame is ever read while the guard is unsatisfied.

Uses Win32 via pywin32. Read-only: enumerating and querying windows touches no
game process memory and injects nothing.
"""

from __future__ import annotations

import ctypes
import time
from collections.abc import Callable
from dataclasses import dataclass

#: Window titles that identify the game. The client is Simplified Chinese, so both
#: the localised and the English titles are accepted.
GAME_TITLES: tuple[str, ...] = ("鸣潮", "Wuthering Waves")

#: Executables that are actually the game. Title matching ALONE is unsafe: a
#: browser tab titled "Items | Wuthering Waves Resource & Companion App" matched
#: GAME_TITLES during testing. In driven mode that would have sent input into a
#: browser. The process name is the authoritative check; the title is a hint.
GAME_PROCESSES: tuple[str, ...] = (
    "client-win64-shipping.exe",  # the Unreal client binary
    "wutheringwaves.exe",
    "wuthering waves.exe",
)


@dataclass(frozen=True, slots=True)
class WindowInfo:
    handle: int
    title: str
    rect: tuple[int, int, int, int]
    """(left, top, right, bottom) in screen coordinates."""
    process: str = ""
    """Lower-cased executable name that owns the window, e.g. "chrome.exe"."""

    @property
    def is_game(self) -> bool:
        return self.process in GAME_PROCESSES

    @property
    def size(self) -> tuple[int, int]:
        left, top, right, bottom = self.rect
        return (right - left, bottom - top)

    @property
    def is_viable(self) -> bool:
        """A minimised or zero-area window cannot be captured usefully."""
        width, height = self.size
        return width > 100 and height > 100


class WindowGuardError(RuntimeError):
    """The expected window is absent, not foreground, or not viable."""


#: Per-monitor DPI awareness v2, as a DPI_AWARENESS_CONTEXT handle value.
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4


def set_dpi_awareness() -> bool:
    """Opt this process into per-monitor DPI awareness. Idempotent, best effort.

    Without it Windows lies about window geometry: on the 3440x1440 machine at
    200% scaling, a DPI-unaware process was told the game window is 1707x1067.
    WGC hands back real pixels regardless, so nothing downstream breaks -- but the
    guard's own report of what it is looking at was wrong by 2x, and a diagnostic
    that misreports the thing it is diagnosing is worse than none.

    Must run before the first window query. Returns False if the OS declined
    (already set, or too old an API), which is not fatal.
    """
    try:
        context = ctypes.c_void_p(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(context):
            return True
    except (AttributeError, OSError):
        pass
    try:  # Windows 8.1 fallback: PROCESS_PER_MONITOR_DPI_AWARE
        return ctypes.windll.shcore.SetProcessDpiAwareness(2) == 0
    except (AttributeError, OSError):
        return False


def process_name(handle: int) -> str:
    """Executable that owns a window, lower-cased. Empty string if unavailable.

    Read-only: this opens the process for *query* rights only. It never reads
    process memory, which the project forbids outright.
    """
    try:
        import win32api
        import win32con
        import win32process
    except ImportError:
        return ""
    try:
        _, pid = win32process.GetWindowThreadProcessId(handle)
        if not pid:
            return ""
        access = win32con.PROCESS_QUERY_LIMITED_INFORMATION
        proc = win32api.OpenProcess(access, False, pid)
        try:
            path = win32process.GetModuleFileNameEx(proc, 0)
        finally:
            win32api.CloseHandle(proc)
        return path.rsplit("\\", 1)[-1].casefold()
    except Exception:
        return ""


def list_windows(visible_only: bool = True) -> list[WindowInfo]:
    """Enumerate top-level windows."""
    import win32gui

    found: list[WindowInfo] = []

    def _collect(handle: int, _: object) -> None:
        if visible_only and not win32gui.IsWindowVisible(handle):
            return
        title = win32gui.GetWindowText(handle)
        if not title:
            return
        try:
            rect = win32gui.GetWindowRect(handle)
        except Exception:
            return
        found.append(
            WindowInfo(
                handle=handle, title=title, rect=rect, process=process_name(handle)
            )
        )

    win32gui.EnumWindows(_collect, None)
    return found


def find_window(
    titles: tuple[str, ...] = GAME_TITLES,
    processes: tuple[str, ...] = GAME_PROCESSES,
) -> WindowInfo | None:
    """Find the game window.

    Requires the owning PROCESS to match. Title is used only to disambiguate when
    a matching process owns several windows -- never on its own, because unrelated
    apps legitimately carry the game's name in their title.
    """
    candidates = [w for w in list_windows() if w.process in processes]
    if not candidates:
        return None
    wanted = [t.casefold() for t in titles]
    for window in candidates:
        folded = window.title.casefold()
        if any(w in folded for w in wanted):
            return window
    return candidates[0]


def foreground_window() -> WindowInfo | None:
    import win32gui

    handle = win32gui.GetForegroundWindow()
    if not handle:
        return None
    try:
        return WindowInfo(
            handle=handle,
            title=win32gui.GetWindowText(handle),
            rect=win32gui.GetWindowRect(handle),
            process=process_name(handle),
        )
    except Exception:
        return None


def require_window(
    titles: tuple[str, ...] = GAME_TITLES, *, must_be_foreground: bool = True
) -> WindowInfo:
    """Return the target window or raise. This is the guard -- it fails closed.

    `must_be_foreground` is True by default and should only be relaxed for
    diagnostics, never for a scan that drives input.
    """
    window = find_window(titles)
    if window is None:
        raise WindowGuardError(
            f"no window owned by {GAME_PROCESSES!r} is open -- refusing to capture"
        )
    if not window.is_viable:
        raise WindowGuardError(
            f"window {window.title!r} is {window.size[0]}x{window.size[1]}; "
            "likely minimised -- refusing to capture"
        )
    if must_be_foreground:
        front = foreground_window()
        if front is None or front.handle != window.handle:
            raise WindowGuardError(
                f"window {window.title!r} is not in the foreground -- refusing to capture"
            )
    return window


def is_game_foreground(window: WindowInfo) -> bool:
    """Is the guarded window the one the user is actually looking at, right now?

    Cheap enough to call on every captured frame, and it is meant to be: focus can
    change between two frames. Re-checks the owning process as well as the handle,
    because a handle outlives the window it named and Windows recycles them.
    """
    front = foreground_window()
    if front is None or front.handle != window.handle:
        return False
    return front.process in GAME_PROCESSES


def wait_for_foreground(
    titles: tuple[str, ...] = GAME_TITLES,
    *,
    timeout: float = 60.0,
    poll: float = 0.25,
    on_wait: Callable[[float], None] | None = None,
    should_abort: Callable[[], bool] | None = None,
    probe: Callable[[], WindowInfo] | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> WindowInfo:
    """Block until the guard passes, then return the approved window.

    Every attempt is the full `require_window` check, so the guard is never
    relaxed -- only retried. `should_abort` is how the panic key gets a say while
    we are waiting; `on_wait` receives the seconds left, for a countdown.

    Raises WindowGuardError if the window does not reach the foreground in time.
    """
    attempt = probe or (lambda: require_window(titles))
    deadline = clock() + timeout
    reason = "the game window never reached the foreground"

    while True:
        if should_abort is not None and should_abort():
            raise WindowGuardError("aborted while waiting for the game window")
        try:
            return attempt()
        except WindowGuardError as exc:
            reason = str(exc)
        remaining = deadline - clock()
        if remaining <= 0:
            raise WindowGuardError(f"waited {timeout:.0f}s -- {reason}")
        if on_wait is not None:
            on_wait(remaining)
        sleep(min(poll, remaining))
