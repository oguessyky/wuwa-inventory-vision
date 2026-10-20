# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""What this machine is, and which PyTorch belongs on it (D70).

Pure functions over probe results, so the decision can be tested without owning
four kinds of computer. `probe()` is the one exception -- it shells out to
nvidia-smi and the OS display list to build a `Machine` -- and it is here rather
than in `tools/setup.py` because the scanner asks the same question at run time
(D77): an NVIDIA machine running CPU torch is a 30x slower scan for no reason.
Nothing here installs anything or touches the network.

The matrix, and why:

* **NVIDIA (Windows)** -> the CUDA 12.8 wheels. They bundle the CUDA runtime, so
  the multi-gigabyte CUDA Toolkit is never needed; what does matter is the
  DRIVER, and an RTX 50-series card needs 571 or newer for sm_120.
* **Intel GPU (Windows)** -> the XPU wheels. `torch.xpu` is the only GPU path a
  Windows machine without an NVIDIA card has: ROCm is Linux-only, and
  torch-directml trails the current torch by years. It covers Arc and the Core
  Ultra iGPUs; an older UHD iGPU falls back to CPU by itself.
* **Apple Silicon** -> stock wheels; torch uses MPS.
* **Anything else** -> the CPU wheels, said plainly. Recognition still works, it
  is just slower -- and OCR is on CPU by default anyway.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import dataclass

#: Where each flavour of torch comes from. None: the default index (PyPI).
INDEXES = {
    "cuda": "https://download.pytorch.org/whl/cu128",
    "xpu": "https://download.pytorch.org/whl/xpu",
    "cpu": "https://download.pytorch.org/whl/cpu",
    "mps": None,
}
#: Blackwell (sm_120) needs this driver or newer; below it CUDA torch loads and
#: then dies on the first kernel.
MIN_NVIDIA_DRIVER = 571.0


@dataclass(frozen=True, slots=True)
class Machine:
    """What the probes found."""

    system: str
    """"Windows", "Darwin", "Linux"."""
    arch: str = ""
    """platform.machine(): "AMD64", "arm64", ..."""
    nvidia: str | None = None
    """The NVIDIA driver version, or None when there is no NVIDIA card."""
    gpus: tuple[str, ...] = ()
    """Display adapter names, as the OS lists them."""

    @property
    def windows(self) -> bool:
        return self.system == "Windows"

    @property
    def macos(self) -> bool:
        return self.system == "Darwin"

    @property
    def apple_silicon(self) -> bool:
        return self.macos and self.arch in ("arm64", "aarch64")

    @property
    def intel_gpu(self) -> bool:
        """An Intel GPU torch's XPU backend can use (Arc, or a Core Ultra iGPU)."""
        return any(
            "intel" in g.lower() and any(k in g.lower() for k in ("arc", "ultra", "iris", "xe"))
            for g in self.gpus
        )

    @property
    def amd_gpu(self) -> bool:
        return any(("amd" in g.lower() or "radeon" in g.lower()) for g in self.gpus)


@dataclass(frozen=True, slots=True)
class Plan:
    """What to install, and what to say about it."""

    flavour: str
    """cuda | xpu | mps | cpu -- the key into INDEXES."""
    index: str | None
    extras: tuple[str, ...]
    """The pyproject extras to sync."""
    notes: tuple[str, ...] = ()
    """Lines the user should read before anything is installed."""
    blocked: str | None = None
    """Set when this machine cannot run the scanner at all."""

    @property
    def gpu(self) -> bool:
        return self.flavour != "cpu"


def nvidia_driver() -> str | None:
    """The NVIDIA driver version from nvidia-smi, or None when there is no card."""
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        out = subprocess.run(  # noqa: S603 -- a fixed executable, no shell
            [exe, "--query-gpu=driver_version", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=20, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    line = out.stdout.strip().splitlines()
    return line[0].strip() if line and line[0].strip() else None


def adapters() -> tuple[str, ...]:
    """Display adapter names, as the OS lists them."""
    if platform.system() == "Windows":
        shell = shutil.which("powershell") or shutil.which("pwsh")
        if not shell:
            return ()
        command = "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"
        args = [shell, "-NoProfile", "-Command", command]
    elif platform.system() == "Darwin":
        args = ["/usr/sbin/system_profiler", "SPDisplaysDataType"]
    else:
        return ()
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=60, check=False)  # noqa: S603
    except (OSError, subprocess.SubprocessError):
        return ()
    if platform.system() == "Darwin":
        return tuple(
            line.split(":", 1)[1].strip()
            for line in out.stdout.splitlines() if "Chipset Model:" in line
        )
    return tuple(x.strip() for x in out.stdout.splitlines() if x.strip())


def probe() -> Machine:
    """What this computer is, as far as the OS will say."""
    return Machine(
        system=platform.system(), arch=platform.machine(),
        nvidia=nvidia_driver(), gpus=adapters(),
    )


def cuda_offer(machine: Machine, cuda_available: bool) -> Plan | None:
    """The install to offer when this machine has an NVIDIA card and CPU torch.

    None when there is nothing to offer: no card, or torch already sees it. A
    driver too old for the card is still offered -- the wheels are only half the
    fix then -- but the note says so, because installing alone would not help.
    """
    if cuda_available or not machine.nvidia or not machine.windows:
        return None
    return plan_for(machine)


def old_driver(version: str | None) -> bool:
    """True when an NVIDIA driver is too old for a 50-series card."""
    if not version:
        return False
    try:
        return float(".".join(version.split(".")[:2])) < MIN_NVIDIA_DRIVER
    except ValueError:
        return False


def plan_for(machine: Machine) -> Plan:
    """Which torch this machine gets, and what the user needs to know."""
    notes: list[str] = []

    if machine.macos:
        # Capture is Windows Graphics Capture today, so a Mac can run the pages
        # and the planner but not a scan (D70).
        extras = ("recognition", "capture-macos")
        if machine.apple_silicon:
            notes.append("Apple Silicon: torch will use MPS for recognition.")
        else:
            notes.append("Intel Mac: recognition runs on CPU.")
        notes.append(
            "Capture goes through the window server (pyobjc): allow Screen Recording "
            "for your terminal the first time."
        )
        return Plan(
            flavour="mps" if machine.apple_silicon else "cpu",
            index=INDEXES["mps"] if machine.apple_silicon else INDEXES["cpu"],
            extras=extras,
            notes=tuple(notes),
        )

    if not machine.windows:
        return Plan(
            flavour="cpu", index=INDEXES["cpu"], extras=("recognition",),
            notes=("Only Windows can capture the game; this installs the pages and the planner.",),
            blocked=f"{machine.system} has no capture backend",
        )

    extras = ("recognition", "capture")
    if machine.nvidia:
        if old_driver(machine.nvidia):
            notes.append(
                f"NVIDIA driver {machine.nvidia} is older than {MIN_NVIDIA_DRIVER:.0f}: "
                "a 50-series card needs a newer one, or CUDA torch will fail on the first scan."
            )
        notes.append(
            "The CUDA 12.8 wheels bundle the CUDA runtime -- the CUDA Toolkit is not needed."
        )
        return Plan(flavour="cuda", index=INDEXES["cuda"], extras=extras, notes=tuple(notes))

    if machine.intel_gpu:
        notes.append("Intel GPU found: installing the XPU wheels (torch.xpu).")
        notes.append(
            "It needs a recent Intel graphics driver; without one torch falls back to CPU."
        )
        return Plan(flavour="xpu", index=INDEXES["xpu"], extras=extras, notes=tuple(notes))

    if machine.amd_gpu:
        notes.append(
            "AMD on Windows has no torch backend (ROCm is Linux-only), so recognition runs on CPU."
        )
    notes.append("Recognition on CPU is ~30x slower than a GPU, and just as accurate.")
    return Plan(flavour="cpu", index=INDEXES["cpu"], extras=extras, notes=tuple(notes))
