# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Shortcuts on the Desktop and in the Start menu (D224).

The user, 2026-10-28: "is it possible to made able for user to add a shortcut to their desktop
or start menu?". A shortcut opens one of the package's own double-click files (D184), with the
app's icon (`assets/wuwa.ico`):

- the Desktop gets the two used every day: scan, and the pages;
- the Start menu gets a folder, `WuWa Inventory Vision`, with every one but Setup.

Setup asks before it makes them, as it asks before every step; `wuwa shortcuts` makes them later
and `wuwa shortcuts --remove` takes them away -- only its own, by name, and the Start menu's
folder only when nothing else is left in it. Windows only for now: a Mac has no Start menu.

The plan and the script are pure; `make()` hands the script to PowerShell's own shortcut maker
(WScript.Shell), encoded, so no name or folder in it can be misread as a command.
"""

from __future__ import annotations

import base64
import subprocess
from dataclasses import dataclass
from pathlib import Path

#: The Start menu's folder for them, and the word each name starts with, so a search finds them.
#: The names are English (the user, 2026-10-28: "the shortcut should use the english name tho").
APP = "WuWa Inventory Vision"
PREFIX = "WuWa"
#: The app's own icon, in the package.
ICON = Path("assets") / "wuwa.ico"
#: Each double-click file (its name after the step's number) and what its shortcut says.
WHAT = {
    "连接服务器 Connect server": "连接服务器 · Connect this scanner to its server",
    "扫描 Scan": "扫描背包 · Scan the bag",
    "总览 Dashboard": "打开页面 · Open the pages",
    "更新 Update": "更新扫描端 · Update this scanner to its server's version",
}
DESKTOP = ("扫描 Scan", "总览 Dashboard")
MENU = ("连接服务器 Connect server", "扫描 Scan", "总览 Dashboard", "更新 Update")


@dataclass(frozen=True)
class Shortcut:
    name: str          # the .lnk's name, without .lnk
    target: Path       # the double-click file it opens
    place: str         # "desktop" or "menu"
    about: str         # what it says when the pointer rests on it


def launchers(folder: Path) -> dict[str, Path]:
    """The package's double-click files, by their name after the number: "扫描 Scan"."""
    found = {}
    for path in folder.glob("* *.cmd"):
        number, _, name = path.stem.partition(" ")
        if number.isdigit():
            found[name] = path
    return found


def plan(folder: Path, system: str) -> list[Shortcut]:
    """The shortcuts this package gets on this system: none in a checkout, none off Windows."""
    if not system.startswith("win"):
        return []
    found = launchers(folder)
    # named in English, the launcher's own English half: "扫描 Scan" -> "WuWa Scan"
    return [Shortcut(f"{PREFIX} {name.split(' ', 1)[-1]}", found[name], place, WHAT[name])
            for place, names in (("desktop", DESKTOP), ("menu", MENU))
            for name in names if name in found]


def _quoted(text: str | Path) -> str:
    """A PowerShell string that is only ever a string: '…', with ' doubled."""
    return "'" + str(text).replace("'", "''") + "'"


#: Windows' own shortcut maker, its Unicode interface (IShellLinkW). WScript.Shell, the usual
#: way from PowerShell, refuses any name outside the system's code page -- and every launcher is
#: named in Chinese ("2 扫描 Scan.cmd"): on an English Windows it failed with "Value does not
#: fall within the expected range". PowerShell compiles this once per run (Add-Type).
LINK = r"""
using System;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
using System.Text;

[ComImport, Guid("00021401-0000-0000-C000-000000000046")]
class ShellLink {}

[ComImport, InterfaceType(ComInterfaceType.InterfaceIsIUnknown),
 Guid("000214F9-0000-0000-C000-000000000046")]
interface IShellLinkW {
  void GetPath([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder file, int size,
               IntPtr data, uint flags);
  void GetIDList(out IntPtr list);
  void SetIDList(IntPtr list);
  void GetDescription([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder name, int size);
  void SetDescription([MarshalAs(UnmanagedType.LPWStr)] string name);
  void GetWorkingDirectory([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder dir, int size);
  void SetWorkingDirectory([MarshalAs(UnmanagedType.LPWStr)] string dir);
  void GetArguments([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder args, int size);
  void SetArguments([MarshalAs(UnmanagedType.LPWStr)] string args);
  void GetHotkey(out short key);
  void SetHotkey(short key);
  void GetShowCmd(out int show);
  void SetShowCmd(int show);
  void GetIconLocation([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder path, int size,
                       out int index);
  void SetIconLocation([MarshalAs(UnmanagedType.LPWStr)] string path, int index);
  void SetRelativePath([MarshalAs(UnmanagedType.LPWStr)] string path, uint reserved);
  void Resolve(IntPtr window, uint flags);
  void SetPath([MarshalAs(UnmanagedType.LPWStr)] string file);
}

public static class WuwaShortcut {
  public static void Make(string lnk, string target, string dir, string icon, string about) {
    IShellLinkW link = (IShellLinkW)new ShellLink();
    link.SetPath(target);
    link.SetWorkingDirectory(dir);
    link.SetIconLocation(icon, 0);
    link.SetDescription(about);
    ((IPersistFile)link).Save(lnk, true);
  }
}
"""


def script(shortcuts: list[Shortcut], folder: Path, remove: bool = False) -> str:
    """The PowerShell that makes them (or takes them away), saying each one it touched."""
    lines = [
        "$ErrorActionPreference = 'Stop'",
        "$ProgressPreference = 'SilentlyContinue'",             # no progress records in the output
        "[Console]::OutputEncoding = [Text.Encoding]::UTF8",    # the names are Chinese
        "$desk = [Environment]::GetFolderPath('Desktop')",
        f"$menu = Join-Path ([Environment]::GetFolderPath('Programs')) {_quoted(APP)}",
    ]
    if not remove:
        # a here-string ends only at '@ at the start of a line, which LINK never has
        lines += ["Add-Type -TypeDefinition @'", LINK.strip("\n"), "'@",
                  "New-Item -ItemType Directory -Force -Path $menu | Out-Null"]
    for s in shortcuts:
        where = "$desk" if s.place == "desktop" else "$menu"
        path = f"(Join-Path {where} {_quoted(s.name + '.lnk')})"
        if remove:
            lines.append(f"$p = {path}; if (Test-Path -LiteralPath $p) "
                         "{ Remove-Item -LiteralPath $p; Write-Output \"removed: $p\" }")
            continue
        lines += [
            f"$p = {path}",
            f"[WuwaShortcut]::Make($p, {_quoted(s.target)}, {_quoted(folder)}, "
            f"{_quoted(folder / ICON)}, {_quoted(s.about)})",
            "Write-Output \"added: $p\"",
        ]
    if remove:
        # the folder goes only when it is empty: anything else in it is not ours
        lines.append("if ((Test-Path -LiteralPath $menu) -and "
                     "-not (Get-ChildItem -LiteralPath $menu)) { Remove-Item -LiteralPath $menu }")
    return "\n".join(lines)


def command(shortcuts: list[Shortcut], folder: Path, remove: bool = False) -> list[str]:
    """PowerShell, given the script encoded: no quoting of a name can go wrong on the way."""
    encoded = base64.b64encode(script(shortcuts, folder, remove).encode("utf-16-le")).decode()
    return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded]


def make(shortcuts: list[Shortcut], folder: Path, remove: bool = False) -> int:
    """Run it, and print what PowerShell said it did."""
    done = subprocess.run(command(shortcuts, folder, remove), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    for line in (done.stdout + done.stderr).splitlines():
        if line.strip():
            print(f"  {line}")
    return done.returncode
