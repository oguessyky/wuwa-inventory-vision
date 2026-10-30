# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""A clean uninstall (D232).

The user, 2026-10-28: "rmb to add an uninstall path for it yah (so people can clean uninstall the
application if needed)". Asked, they chose: everything goes -- the shortcuts, the installed
environment, the model, the program's folder -- and it asks first whether the scans and settings
(the `data` folder) go too, keeping them unless told; and it starts like every other step, from a
double-click file, `5 卸载 Uninstall`.

A program cannot delete the folder it runs from (its own Python is in it, and on Windows a file in
use cannot be removed), so the last step is a small script started on its own: it waits for this
process to end, then removes what it was given, trying again for a minute while a file is still
held. It runs only on an unzipped package -- one with the `VERSION` the zips add, and no `.git` --
so a checkout of the source is never touched.

uv itself and its download cache are shared with anything else that uses them, so they stay; the
last words say how to remove them.
"""

from __future__ import annotations

import base64
import contextlib
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

#: How long the last step keeps trying while a file is still held (seconds).
TRIES = 60


def is_package(folder: Path) -> bool:
    """An unzipped package, and nothing else: the zips add VERSION; a checkout has .git."""
    folder = Path(folder)
    return (folder / "VERSION").is_file() and not (folder / ".git").exists()


def targets(folder: Path, keep_data: bool) -> list[Path]:
    """What goes: the whole folder, or all of it but `data`."""
    folder = Path(folder)
    if not keep_data:
        return [folder]
    return sorted(p for p in folder.iterdir() if p.name != "data")


def _ps(text: str | Path) -> str:
    return "'" + str(text).replace("'", "''") + "'"


def finish_command(folder: Path, keep_data: bool, pid: int, system: str) -> list[str]:
    """The last step, as a command: wait for `pid` to end, then remove. Pure; `finish` runs it."""
    folder = Path(folder)
    if system.startswith("win"):
        what = (f"Get-ChildItem -LiteralPath {_ps(folder)} -Force | "
                "Where-Object { $_.Name -ne 'data' } | ForEach-Object { $_.FullName }"
                if keep_data else f"@({_ps(folder)})")
        script = "\n".join([
            "$ErrorActionPreference = 'SilentlyContinue'",
            "$ProgressPreference = 'SilentlyContinue'",
            f"Wait-Process -Id {pid} -ErrorAction SilentlyContinue",
            f"for ($i = 0; $i -lt {TRIES}; $i++) {{",
            f"  $left = @({what} | Where-Object {{ Test-Path -LiteralPath $_ }})",
            "  if ($left.Count -eq 0) { break }",
            "  foreach ($t in $left) { Remove-Item -LiteralPath $t -Recurse -Force }",
            "  Start-Sleep -Seconds 1",   # a file still held: once more
            "}",
        ])
        encoded = base64.b64encode(script.encode("utf-16-le")).decode()
        return ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded]
    quoted = "'" + str(folder).replace("'", "'\\''") + "'"
    if keep_data:
        remove = f"find {quoted} -mindepth 1 -maxdepth 1 ! -name data -exec rm -rf {{}} +"
        gone = f'[ -z "$(ls -A {quoted} | grep -vx data)" ]'
    else:
        remove, gone = f"rm -rf {quoted}", f"[ ! -e {quoted} ]"
    script = "\n".join([
        f"while kill -0 {pid} 2>/dev/null; do sleep 1; done",
        'cd "$HOME"',
        "i=0",
        f"while [ $i -lt {TRIES} ]; do",
        f"  {remove} 2>/dev/null",
        f"  {gone} && break",
        "  i=$((i+1)); sleep 1",
        "done",
    ])
    return ["/bin/sh", "-c", script]


def finish(folder: Path, keep_data: bool, pid: int) -> None:
    """Start the last step on its own, so it outlives this process."""
    command = finish_command(folder, keep_data, pid, sys.platform)
    if sys.platform.startswith("win"):
        flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                 | subprocess.CREATE_NO_WINDOW)
        subprocess.Popen(command, creationflags=flags, close_fds=True, cwd=Path.home())
    else:
        subprocess.Popen(command, start_new_session=True, close_fds=True, cwd=Path.home())


def run(folder: Path, answer: Callable[[str], str] = input) -> int:
    """Ask, take the shortcuts away, and hand the rest to the last step."""
    import os

    from . import shortcuts

    folder = Path(folder).resolve()
    if not is_package(folder):
        print(f"not an unzipped package: {folder} -- nothing is removed")
        return 2
    print(f"Uninstall WuWa Inventory Vision from {folder}")
    print("  removes: the shortcuts, the installed environment, the recognition model, "
          "the program's files")

    def yes(question: str) -> bool:
        try:
            return answer(f"{question} [y/N] ").strip().lower() in ("y", "yes")
        except EOFError:
            return False

    if not yes("Uninstall it?"):
        print("nothing removed")
        return 1
    keep = not yes("Also delete your scans and settings (the data folder)?")
    every = shortcuts.everything(folder, sys.platform)
    if every:
        shortcuts.make(every, folder, remove=True)
    finish(folder, keep, os.getpid())
    if keep:
        print(f"done: your scans and settings stay in {folder / 'data'} -- copy them to a new "
              "install's folder to carry on, or delete that folder")
    else:
        print(f"done: {folder} is removed as soon as this window closes")
    print("  uv and its download cache are shared, so they stay: `uv cache clean` empties the "
          "cache; uv itself is removed like any other program")
    with contextlib.suppress(EOFError):
        answer("Press Enter to close ")
    return 0
