# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Set the project up on this machine: the right PyTorch, then the model (D70).

    uv run python tools/setup.py          # ask before each step
    uv run python tools/setup.py --yes    # take every default
    uv run python tools/setup.py --check  # say what it found, install nothing

What it does, in order: work out what this computer is, say so, install the
dependencies with the PyTorch flavour that fits (CUDA for NVIDIA, XPU for an
Intel GPU, MPS on Apple Silicon, else CPU), fetch the DINOv2 weights, download
the catalogue from Kuro's wiki if it is not there yet, and check that torch
really sees the device.

The catalogue step is the one thing here that goes near the network beyond the
package index, and it only runs because the user ran this script and said yes
(D46, D85) -- `--zip` skips the wiki entirely and unpacks the icon archive
instead.

The decision itself lives in `wuwa_vision.setup_env`, which is pure and tested;
this file only probes and runs commands.
"""

from __future__ import annotations

import argparse
import contextlib
import shutil
import subprocess
import sys
from pathlib import Path

# A stock Windows console is cp1252 and this script prints Chinese step names:
# without this it dies on a print, which is a poor first impression.
for stream in (sys.stdout, sys.stderr):
    with contextlib.suppress(AttributeError, OSError):
        stream.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wuwa_vision import shortcuts  # noqa: E402
from wuwa_vision.setup_env import Machine, Plan, plan_for, probe  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def say(machine: Machine, plan: Plan) -> None:
    print(f"machine   : {machine.system} {machine.arch}")
    for gpu in machine.gpus:
        print(f"  gpu     : {gpu}")
    if machine.nvidia:
        print(f"  driver  : NVIDIA {machine.nvidia}")
    print(f"torch     : {plan.flavour}" + (f"  ({plan.index})" if plan.index else "  (PyPI)"))
    print(f"extras    : {', '.join(plan.extras)}")
    for note in plan.notes:
        print(f"  note    : {note}")
    if plan.blocked:
        print(f"  WARNING : {plan.blocked}")


def ask(question: str, assume_yes: bool, default: bool = True) -> bool:
    """A yes or no, Enter taking the default; --yes takes every default."""
    if assume_yes:
        return default
    try:
        said = input(f"{question} {'[Y/n]' if default else '[y/N]'} ").strip().lower()
    except EOFError:  # non-interactive: do nothing rather than guess
        return False
    return default if not said else said in ("y", "yes")


def run(command: list[str]) -> int:
    print("  $", " ".join(command))
    return subprocess.run(command, cwd=ROOT, check=False).returncode  # noqa: S603


def install(plan: Plan, assume_yes: bool, python: str | None = None) -> int:
    uv = shutil.which("uv")
    if not uv:
        print("uv is not installed: winget install astral-sh.uv   (or pip install uv)")
        return 1
    extras = [arg for extra in plan.extras for arg in ("--extra", extra)]
    # on the Python setup.ps1 found -- the release's own (D175) is on no PATH for uv to find
    on = ["--python", python] if python else []
    if ask("install the dependencies?", assume_yes) and (code := run([uv, "sync", *extras, *on])):
        return code
    # torch comes from its own index, and pyproject pins the CUDA one: on any
    # other machine the right wheel has to replace it afterwards.
    if (
        plan.index
        and plan.flavour != "cuda"
        and ask(f"install the {plan.flavour} build of torch?", assume_yes)
        and (code := run([uv, "pip", "install", "--index-url", plan.index,
                          "--reinstall", "torch", "torchvision"]))
    ):
        return code
    if ask("download the DINOv2 weights (~346 MB)?", assume_yes) and (
        code := run([uv, "run", "python", "tools/fetch_model.py"])
    ):
        return code
    return 0


#: The catalogue fetches, in the order the 更新 page runs them (update.STEPS).
CATALOGUE_STEPS = (
    ("物品与图标", "fetch_catalogue.py"),
    ("料理与物品资料", "fetch_recipes.py"),
    ("共鸣者与武器", "fetch_builds.py"),
    ("共鸣者头像", "fetch_icons.py"),
    ("等级经验表", "fetch_levels.py"),
    ("商店货品", "fetch_shops.py"),
    ("首领头像", "fetch_bosses.py"),
)


def catalogue(assume_yes: bool, zip_source: str | None, scanner: bool = False) -> None:
    """Download the catalogue when it is not there (D85).

    Every page except the raw scan reads from it: names, icons, what each
    resonator and weapon costs, recipes, the level tables. Leaving it to a
    follow-up command meant a fresh install looked broken.

    A scanner that sends to a home (D145, D174) is given it by the home before
    every scan, so it fetches nothing of its own.
    """
    index = ROOT / "data" / "catalogue" / "index.json"
    have = index.exists()
    print()
    if scanner:
        print("catalogue : the server sends it before each scan -- nothing to download here")
        return
    if have and not zip_source:
        print("catalogue : already downloaded (update it any time on the 更新 page)")
        return
    print("catalogue : items, recipes, resonators, weapons, icons and level tables")
    print("            from Kuro's wiki (wiki.kurobbs.com) -- the only network")
    print("            call this project makes, and only because you are here.")
    if not ask("download the catalogue now?", assume_yes):
        print("  skipped -- the 更新 page can do it later.")
        return
    uv = shutil.which("uv") or "uv"
    for label, tool, *_ in CATALOGUE_STEPS:
        extra = ["--from-zip", zip_source] if (zip_source and tool == "fetch_catalogue.py") else []
        print(f"  {label}")
        if run([uv, "run", "python", f"tools/{tool}", *extra]):
            print(f"  {label} failed -- the 更新 page can retry it later.")


def verify() -> None:
    """Ask torch what it actually got. A plan that did not happen is worth knowing."""
    uv = shutil.which("uv") or "uv"
    code = (
        "import torch;"
        "xpu = getattr(torch, 'xpu', None);"
        "mps = getattr(torch.backends, 'mps', None);"
        "print('torch', torch.__version__);"
        "print('cuda', torch.cuda.is_available());"
        "print('xpu', bool(xpu and xpu.is_available()));"
        "print('mps', bool(mps and mps.is_available()))"
    )
    run([uv, "run", "python", "-c", code])


def add_shortcuts(assume_yes: bool) -> None:
    """Shortcuts, if this is a package on Windows or a Mac (D224): a question per place, as not
    everyone wants both; Connect server only on a yes, as it is done once (D231)."""
    every = shortcuts.everything(ROOT, sys.platform)
    if not every:
        return
    places = []
    if ask("add shortcuts to the Desktop?", assume_yes):
        places.append("desktop")
    menu_question = ("add shortcuts to Applications (Launchpad, Spotlight)?"
                     if sys.platform == "darwin" else "add shortcuts to the Start menu?")
    if ask(menu_question, assume_yes):
        places.append("menu")
    connect = (bool(places) and any(s.name.endswith("Connect server") for s in every)
               and ask("also a shortcut for Connect server?", assume_yes, default=False))
    plan = shortcuts.plan(ROOT, sys.platform, tuple(places), connect)
    if plan and shortcuts.make(plan, ROOT):
        print("  the shortcuts could not be made: the double-click files still work")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="take every default")
    parser.add_argument("--check", action="store_true", help="only say what it found")
    parser.add_argument(
        "--zip", metavar="URL_OR_PATH",
        help="install the catalogue icons from this archive instead of the wiki",
    )
    parser.add_argument(
        "--python", metavar="PATH",
        help="build the environment on this Python 3.12 (setup.ps1 passes the one it found)",
    )
    parser.add_argument(
        "--scanner", action="store_true",
        help="this machine scans for a server: skip the catalogue, the server sends it",
    )
    args = parser.parse_args()

    machine = probe()
    plan = plan_for(machine)
    say(machine, plan)
    if args.check:
        return 0
    print()
    code = install(plan, args.yes, args.python)
    if code:
        return code
    catalogue(args.yes, args.zip, args.scanner)
    print()
    verify()
    add_shortcuts(args.yes)
    if args.scanner and not plan.blocked:
        print("\nnext:  uv run python -m wuwa_vision server set <the server's address> <its key>")
        print("       uv run python -m wuwa_vision live --identify   (scan the bag)")
        return 0
    print("\nnext:  uv run python -m wuwa_vision serve      (the pages)")
    if plan.blocked:
        print(f"       scanning is not available here: {plan.blocked}")
    else:
        print("       uv run python -m wuwa_vision live --identify   (scan the bag)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
