# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Reach the main app from the user's other devices, over their own tailnet (D108).

The app still binds `127.0.0.1` and nothing else: this never opens a port on the
LAN or the internet. Where Tailscale is installed and connected, `tailscale
serve` is run beside the app as a child process; it listens on the machine's
tailnet address only and passes requests to the loopback port. That reaches the
devices signed in to the same tailnet and nobody else.

It lasts exactly as long as the app runs. The share is started in the
foreground, so Tailscale drops it when that process ends: nothing is written to
Tailscale's configuration and nothing survives a reboot. And that process is
tied to the app's own life (`_die_with_parent`), so a share cannot outlive an
app that was killed rather than closed -- left behind, it would go on pointing
at the port, and at whatever opened it next. `tailscale funnel` (the
public-internet variant) is never used.

There is no login on the app itself. Anyone on the tailnet can see the inventory
and use every button, which is why `serve --local` exists and why the address
is printed at start-up instead of being assumed.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field

#: How long `tailscale` gets to answer before it is treated as not there (s).
ASK_TIMEOUT = 5.0
#: A share that failed says so at once and exits; one still running after this is up (s).
SETTLE = 1.5


@dataclass
class Share:
    """A running share: where the app is on the tailnet, and how to end it."""

    url: str
    process: subprocess.Popen
    #: Whatever ties the process to this one's life; held so it is not collected.
    leash: object = field(default=None, repr=False)

    def stop(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=ASK_TIMEOUT)
            except subprocess.TimeoutExpired:
                self.process.kill()


def _die_with_parent(process: subprocess.Popen) -> object:
    """Make `process` end when this one does, however this one ends.

    Windows: a job object that kills what is in it when its last handle closes
    -- and the only handle is ours, so the system closes it even if we are
    killed outright. Elsewhere the normal exit path (`Share.stop`) is all there
    is. Returns what must be kept alive for the tie to hold.
    """
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    class BasicLimits(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                    ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    class IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class ExtendedLimits(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", BasicLimits), ("IoInfo", IoCounters),
                    ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t)]

    kill_on_close, extended_limits = 0x2000, 9
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.SetInformationJobObject.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    job = kernel.CreateJobObjectW(None, None)
    if not job:
        return None
    limits = ExtendedLimits()
    limits.BasicLimitInformation.LimitFlags = kill_on_close
    tied = (kernel.SetInformationJobObject(job, extended_limits, ctypes.byref(limits),
                                           ctypes.sizeof(limits))
            and kernel.AssignProcessToJobObject(job, wintypes.HANDLE(int(process._handle))))
    return job if tied else None


def tailnet_name(exe: str) -> tuple[str | None, str]:
    """This machine's name on the tailnet, or None and why not."""
    try:
        # Tailscale writes UTF-8 (device and user names); the console's own
        # code page would choke on it and leave nothing to read.
        reply = subprocess.run([exe, "status", "--json"], capture_output=True, timeout=ASK_TIMEOUT,
                               check=False, encoding="utf-8", errors="replace")
        status = json.loads(reply.stdout or "{}")
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return None, "Tailscale did not answer"
    if status.get("BackendState") != "Running":
        return None, "Tailscale is not connected"
    name = str((status.get("Self") or {}).get("DNSName") or "").rstrip(".")
    return (name, "") if name else (None, "this device has no tailnet name")


def open_share(port: int) -> tuple[Share | None, str]:
    """Share 127.0.0.1:`port` with the tailnet: the share, or None and why not."""
    exe = shutil.which("tailscale")
    if exe is None:
        return None, "Tailscale is not installed"
    name, why = tailnet_name(exe)
    if name is None:
        return None, why
    try:
        process = subprocess.Popen(
            [exe, "serve", f"--http={port}", f"http://127.0.0.1:{port}"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            encoding="utf-8", errors="replace",
        )
    except OSError as error:
        return None, str(error)
    leash = _die_with_parent(process)
    try:
        process.wait(timeout=SETTLE)
    except subprocess.TimeoutExpired:
        return Share(url=f"http://{name}:{port}", process=process, leash=leash), ""
    reason = (process.stderr.read() if process.stderr else "").strip().splitlines()
    return None, reason[-1] if reason else "tailscale serve stopped at once"


def share(port: int, say: Callable[[str], None] = print) -> Share | None:
    """Share the main app. Returns None, having said why, when it cannot: the app
    is then simply local, which is always safe."""
    shared, why = open_share(port)
    if shared is None:
        say(f"  tailnet : not shared ({why})")
        return None
    say(f"  tailnet : {shared.url}")
    say("            your own Tailscale devices only; `serve --local` keeps it to this PC")
    return shared
