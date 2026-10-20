# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Global panic key (PLAN.md D15, guardrail 1).

One hotkey that halts capture and input immediately, live for as long as the tool
is armed. It exists for the case where everything else has gone wrong, so it is
deliberately the simplest mechanism available: a Win32 global hotkey and a
threading.Event that every loop checks.

This REGISTERS a hotkey; it does not hook or intercept the keyboard. `RegisterHotKey`
is the documented, benign API that any application may call, and the OS -- not this
process -- decides what to deliver. No input is captured, logged, or forwarded.

Note the asymmetry with D6: passive scanning avoids input hooks entirely, but a
panic key must fire even when the game has focus, and a registered hotkey is the
only way to do that without a hook. It listens for exactly one key combination and
does nothing else.

On macOS there is no equivalent that does not need Accessibility permission --
and a global key watcher IS the keyboard hook this project refuses to install.
What there is instead (D71): macOS has no driven-input backend at all, so the
only thing to stop is a passive read loop, and Ctrl+C in the terminal that
started it stops that. `MacPanicKey` arms a SIGINT handler, so `wuwa live` still
refuses to start unless it has a way to be stopped -- the rule that matters --
without pretending to a hotkey it cannot register.
"""

from __future__ import annotations

import contextlib
import ctypes
import signal
import sys
import threading
from dataclasses import dataclass, field

if sys.platform == "win32":  # wintypes does not exist anywhere else
    from ctypes import wintypes

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312

#: Virtual-key codes for keys worth binding.
VK = {
    "F9": 0x78,
    "F10": 0x79,
    "F11": 0x7A,
    "F12": 0x7B,
    "F24": 0x87,
    "PAUSE": 0x13,
    "SCROLLLOCK": 0x91,
}

#: F9 is rarely bound in-game and needs no modifier -- a panic key you have to
#: chord is a panic key you fumble. Not F12: it was taken on the user's machine
#: (error 1409) and is the OS debugger hotkey on others (D26).
DEFAULT_KEY = "F9"

#: The Mac's only stop (D71), named where it has to be pressed: the game window
#: has focus while scanning, and Ctrl+C there does nothing.
MAC_KEY = "Ctrl+C in this terminal"


#: The failures worth naming. 1409 is the common one; F12 is also reserved by the
#: OS debugger on many machines, which surfaces as a plain refusal.
_REGISTER_ERRORS = {
    0: "refused by Windows (F12 is reserved as the debugger hotkey on some systems)",
    1409: "already registered by another application",
}


class PanicKeyError(RuntimeError):
    """The hotkey could not be registered (usually: already taken)."""


@dataclass
class MacPanicKey:
    """Ctrl+C in the terminal that started the scan, as an Event (D71).

    Same contract as `PanicKey`: arm it or do not start. It replaces the SIGINT
    handler while armed and puts the old one back on disarm, so a second Ctrl+C
    after the scan has stopped behaves as it always did.
    """

    key: str = MAC_KEY
    event: threading.Event = field(default_factory=threading.Event)
    _previous: object = field(default=None, repr=False)

    @property
    def triggered(self) -> bool:
        return self.event.is_set()

    def arm(self, timeout: float = 2.0) -> None:  # noqa: ARG002 -- nothing to wait for
        if self._previous is not None:
            return
        try:
            self._previous = signal.signal(signal.SIGINT, self._fire)
        except (ValueError, OSError) as exc:
            # Not the main thread, or no signal support: refuse rather than run
            # with nothing to stop it.
            raise PanicKeyError(f"cannot listen for Ctrl+C here: {exc}") from exc

    def _fire(self, *_: object) -> None:
        self.event.set()

    def disarm(self) -> None:
        if self._previous is not None:
            with contextlib.suppress(ValueError, OSError):
                signal.signal(signal.SIGINT, self._previous)  # type: ignore[arg-type]
            self._previous = None

    def reset(self) -> None:
        self.event.clear()

    def __enter__(self) -> MacPanicKey:
        self.arm()
        return self

    def __exit__(self, *_: object) -> None:
        self.disarm()


@dataclass
class PanicKey:
    """A global hotkey that sets an Event when pressed.

    Use as a context manager, and check `triggered` inside every loop that
    captures or synthesises input.
    """

    key: str = DEFAULT_KEY
    modifiers: int = MOD_NOREPEAT
    event: threading.Event = field(default_factory=threading.Event)

    _thread: threading.Thread | None = field(default=None, repr=False)
    _stop: threading.Event = field(default_factory=threading.Event, repr=False)
    _ready: threading.Event = field(default_factory=threading.Event, repr=False)
    _error: str | None = field(default=None, repr=False)
    _hotkey_id: int = field(default=1, repr=False)

    @property
    def triggered(self) -> bool:
        return self.event.is_set()

    def arm(self, timeout: float = 2.0) -> None:
        """Register the hotkey and start listening. Raises if registration fails."""
        if self._thread is not None:
            return
        vk = VK.get(self.key.upper())
        if vk is None:
            raise PanicKeyError(f"unknown key {self.key!r}; known: {sorted(VK)}")

        self._stop.clear()
        self._ready.clear()
        self._error = None
        self._thread = threading.Thread(
            target=self._run, args=(vk,), name="panic-key", daemon=True
        )
        self._thread.start()
        if not self._ready.wait(timeout):
            raise PanicKeyError("panic key thread did not start in time")
        if self._error:
            self._thread = None
            raise PanicKeyError(self._error)

    def disarm(self) -> None:
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=2.0)

    def reset(self) -> None:
        self.event.clear()

    def _run(self, vk: int) -> None:
        # use_last_error=True or GetLastError is meaningless here: ctypes resets
        # it, and every registration failure reported "error 0".
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        # RegisterHotKey and the message loop MUST share a thread: the hotkey
        # message is posted to the registering thread's queue.
        if not user32.RegisterHotKey(None, self._hotkey_id, self.modifiers, vk):
            code = ctypes.get_last_error()
            detail = _REGISTER_ERRORS.get(code, f"error {code}")
            self._error = f"RegisterHotKey failed for {self.key}: {detail}"
            self._ready.set()
            return
        self._ready.set()
        try:
            msg = wintypes.MSG()
            while not self._stop.is_set():
                # PeekMessage rather than GetMessage: GetMessage blocks forever and
                # would ignore disarm() until the next key event.
                if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                    if msg.message == WM_HOTKEY:
                        self.event.set()
                else:
                    self._stop.wait(0.02)
        finally:
            user32.UnregisterHotKey(None, self._hotkey_id)

    def __enter__(self) -> PanicKey:
        self.arm()
        return self

    def __exit__(self, *exc: object) -> None:
        self.disarm()


def key_is_available(key: str) -> bool:
    """Can this hotkey be claimed right now? Claims it and lets go immediately."""
    probe = PanicKey(key=key)
    try:
        probe.arm()
    except PanicKeyError:
        return False
    probe.disarm()
    return True


def available_keys() -> list[str]:
    """Keys that register right now, in preference order.

    The point is a usable error: "F12 is taken" without saying what is not taken
    leaves the user guessing, and a panic key that cannot be armed stops the run
    outright.
    """
    return [key for key in VK if key_is_available(key)]


def panic_key(key: str = DEFAULT_KEY) -> PanicKey | MacPanicKey:
    """The stop mechanism this machine has (D71).

    Windows registers a global hotkey; macOS listens for Ctrl+C, because the only
    alternative there is the keyboard hook this project refuses to install. Both
    satisfy the rule that matters: `wuwa live` does not start without one.
    """
    if sys.platform == "darwin":
        return MacPanicKey()
    return PanicKey(key=key)
