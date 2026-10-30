# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Shortcuts on the Desktop and in the Start menu, or a Mac's Applications (D224, D231).

The user, 2026-10-28: "is it possible to made able for user to add a shortcut to their desktop
or start menu?"; then "not all people want it in both place, and I think you forgot to support
for mac. ... shortcut for connect server I dont think is needed (you may put it as optional". A
shortcut opens one of the package's own double-click files (D184), with the app's icon:

- the Desktop gets the two used every day: scan, and the pages;
- the "menu" -- the Start menu's `WuWa Inventory Vision` folder, or a Mac's Applications, where
  Launchpad and Spotlight find them -- gets every one but Setup and Uninstall;
- Connect server only when asked: it is done once.

Setup asks once per place; `wuwa shortcuts` makes them later and `--remove` (and the uninstall,
D232) takes away every one it could have made -- only its own, by name.

Windows: Windows' Unicode shortcut maker, given an encoded PowerShell script, so no name or folder
in it can be misread as a command. A Mac: a `.command` on the Desktop that runs the package's own,
and in Applications a small app that opens it in Terminal, with `assets/wuwa.icns`.
"""

from __future__ import annotations

import base64
import plistlib
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

#: The Start menu's folder for them, and the word each name starts with, so a search finds them.
#: The names are English (the user, 2026-10-28: "the shortcut should use the english name tho").
APP = "WuWa Inventory Vision"
PREFIX = "WuWa"
#: The app's own icon, in the package: Windows', and a Mac's.
ICON = Path("assets") / "wuwa.ico"
ICNS = Path("assets") / "wuwa.icns"
#: Each double-click file (its name after the step's number) and what its shortcut says.
WHAT = {
    "连接服务器 Connect server": "连接服务器 · Connect this scanner to its server",
    "扫描 Scan": "扫描背包 · Scan the bag",
    "总览 Dashboard": "打开页面 · Open the pages",
    "更新 Update": "更新扫描端 · Update this scanner to its server's version",
}
CONNECT = "连接服务器 Connect server"
DESKTOP = ("扫描 Scan", "总览 Dashboard")
MENU = (CONNECT, "扫描 Scan", "总览 Dashboard", "更新 Update")
#: The places: the Desktop, and the "menu" -- the Start menu, or a Mac's Applications.
PLACES = ("desktop", "menu")


@dataclass(frozen=True)
class Shortcut:
    name: str          # the shortcut's name, without .lnk / .command / .app
    target: Path       # the double-click file it opens
    place: str         # "desktop" or "menu"
    about: str         # what it says when the pointer rests on it


def launchers(folder: Path, system: str = sys.platform) -> dict[str, Path]:
    """The package's double-click files, by their name after the number: "扫描 Scan"."""
    suffix = ".command" if system == "darwin" else ".cmd"
    found = {}
    for path in folder.glob(f"* *{suffix}"):
        number, _, name = path.stem.partition(" ")
        if number.isdigit():
            found[name] = path
    return found


def plan(folder: Path, system: str, places: tuple[str, ...] = PLACES,
         connect: bool = False) -> list[Shortcut]:
    """The shortcuts this package gets on this system, in the places asked for: none in a
    checkout, none where neither Windows nor a Mac. Connect server only when asked (D231)."""
    if not (system.startswith("win") or system == "darwin"):
        return []
    found = launchers(folder, system)
    # named in English, the launcher's own English half: "扫描 Scan" -> "WuWa Scan"
    return [Shortcut(f"{PREFIX} {name.split(' ', 1)[-1]}", found[name], place, WHAT[name])
            for place, names in (("desktop", DESKTOP), ("menu", MENU)) if place in places
            for name in names if name in found and (connect or name != CONNECT)]


def everything(folder: Path, system: str) -> list[Shortcut]:
    """Every shortcut this package could have made: what `--remove` and the uninstall take away."""
    return plan(folder, system, PLACES, connect=True)


# --- a Mac -----------------------------------------------------------------------------------

def _mac_paths(s: Shortcut, home: Path) -> Path:
    if s.place == "desktop":
        return home / "Desktop" / f"{s.name}.command"
    return home / "Applications" / f"{s.name}.app"


def mac_apply(shortcuts: list[Shortcut], folder: Path, home: Path,
              remove: bool = False) -> list[Path]:
    """Make them in `home` (or take them away), and return what was touched. The Desktop's is a
    `.command` that runs the package's own -- not a link, which would run it from the Desktop's
    folder; Applications' is a small app that opens it in Terminal, as a double-click does."""
    touched = []
    for s in shortcuts:
        path = _mac_paths(s, home)
        if remove:
            if path.is_dir():
                shutil.rmtree(path)
                touched.append(path)
            elif path.exists():
                path.unlink()
                touched.append(path)
            continue
        if s.place == "desktop":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f'#!/bin/bash\n# {s.about} -- WuWa Inventory Vision (D231)\n'
                            f'exec "{s.target}"\n', "utf-8", newline="\n")
            path.chmod(0o755)
        else:
            contents = path / "Contents"
            (contents / "MacOS").mkdir(parents=True, exist_ok=True)
            (contents / "Resources").mkdir(parents=True, exist_ok=True)
            run = contents / "MacOS" / "run"
            run.write_text(f'#!/bin/bash\nopen -a Terminal "{s.target}"\n', "utf-8", newline="\n")
            run.chmod(0o755)
            icon = folder / ICNS
            if icon.exists():
                shutil.copyfile(icon, contents / "Resources" / "wuwa.icns")
            info = {"CFBundleName": s.name, "CFBundleDisplayName": s.name,
                    "CFBundleIdentifier": "io.github.oguessyky.wuwa." + s.name.split()[-1].lower(),
                    "CFBundleExecutable": "run", "CFBundleIconFile": "wuwa",
                    "CFBundlePackageType": "APPL", "CFBundleVersion": "1",
                    "LSUIElement": True}
            (contents / "Info.plist").write_bytes(plistlib.dumps(info))
        touched.append(path)
    return touched


# --- Windows ---------------------------------------------------------------------------------

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
    """Make them (or take them away) on this machine, and say what was done."""
    if sys.platform == "darwin":
        for path in mac_apply(shortcuts, folder, Path.home(), remove):
            print(f"  {'removed' if remove else 'added'}: {path}")
        return 0
    done = subprocess.run(command(shortcuts, folder, remove), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    for line in (done.stdout + done.stderr).splitlines():
        if line.strip():
            print(f"  {line}")
    return done.returncode
