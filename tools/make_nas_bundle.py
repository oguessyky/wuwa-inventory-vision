# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Lay out what a NAS needs to build and run the home (docs/nas.md, PLAN.md D145).

    uv run python tools/make_nas_bundle.py <folder>            the app, to build there
    uv run python tools/make_nas_bundle.py <folder> --seed     and a first copy of the data
    uv run python tools/make_nas_bundle.py <folder> --check    say what would change; write nothing

`<folder>` is one the NAS can see -- a share, or a folder that syncs to it. This writes:

    <folder>/docker-compose.yaml, setup.sh, .env.example
                                             how to run it (your own .env is never touched)
    <folder>/app/                            the source the image is built from
    <folder>/seed-data/                      with --seed: the database, crops and catalogue

and nothing else. `app/` is made to match the repository exactly (a file that is gone
here is removed there); everything else in the folder is left alone. Only files git
tracks are copied, so nothing of yours that is not part of the project goes along.

The data is copied once. After the home has started it is the only copy that counts:
running `--seed` again would be offering it an old one, so that is refused while a
seed-data folder is still there.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import subprocess
import sys
import tomllib
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy" / "nas"
#: Tailscale's Serve settings and licence: one copy each, for this image and that one (D238).
TAILSCALE = ROOT / "deploy" / "tailscale-image"
#: What the image is built from, besides deploy/nas itself.
SOURCES = ("pyproject.toml", "uv.lock", "README.md", "LICENSE", "NOTICE", "CREDITS.md",
           "TERMS.md", "PRIVACY.md", "PRIVACY.zh-CN.md", "src", "tools", "assets")
#: Of data/, what a home needs: not the model (it recognises nothing), not backups,
#: not recorded runs, not this machine's own note of where its home is.
SEED = ("icons", "catalogue")
#: Written beside app/ by an earlier version of this tool, and now called something else.
RETIRED = ("compose.yaml",)
#: Files that are run on Linux: a carriage return in one stops it starting.
UNIX = {".sh", ".yaml", ".example"}


def tracked(paths: tuple[str, ...]) -> list[str]:
    """The files git tracks under `paths`, as the working tree has them now.

    Run from a release package (D174), which is not a git checkout, it is every file
    under them: the package holds nothing else."""
    if not (ROOT / ".git").exists():
        found = [p for part in paths for p in ((ROOT / part).rglob("*") if (ROOT / part).is_dir()
                                               else [ROOT / part]) if p.is_file()]
        return sorted(p.relative_to(ROOT).as_posix() for p in found
                      if "__pycache__" not in p.parts and p.suffix != ".pyc")
    out = subprocess.run(  # noqa: S603 -- a fixed executable, no shell
        ["git", "-C", str(ROOT), "ls-files", "-z", "--", *paths],  # noqa: S607
        capture_output=True, check=True).stdout.decode("utf-8")
    return sorted(p for p in out.split("\0") if p and (ROOT / p).is_file())


def project_version() -> str:
    """The version pyproject.toml gives the project ("1.0.0")."""
    with (ROOT / "pyproject.toml").open("rb") as f:
        return tomllib.load(f)["project"]["version"]


def version() -> str:
    """What app/VERSION says: "v1.0.0  081a452  2026-10-20 12:45" (D164, D174). From a
    release package, the one it came with."""
    if not (ROOT / ".git").exists() and (ROOT / "VERSION").is_file():
        return (ROOT / "VERSION").read_text(encoding="utf-8")
    def git(*args: str) -> str:
        return subprocess.run(  # noqa: S603
            ["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=False  # noqa: S607
        ).stdout.strip()

    changed = git("status", "--porcelain", "--", *SOURCES, "deploy")
    commit = git("rev-parse", "--short", "HEAD") or "unknown"
    dirty = " +changes not committed" if changed else ""
    return f"v{project_version()}  {commit}{dirty}  {datetime.now():%Y-%m-%d %H:%M}\n"


def content(source: Path) -> bytes:
    data = source.read_bytes()
    return data.replace(b"\r\n", b"\n") if source.suffix in UNIX or source.name == "Dockerfile" \
        else data


def plan(dest: Path) -> tuple[dict[Path, bytes | Path], list[Path]]:
    """dest file -> its content (or the file to copy), and the files of app/ that must go."""
    want: dict[Path, bytes | Path] = {
        dest / "docker-compose.yaml": content(DEPLOY / "docker-compose.yaml"),
        dest / ".env.example": content(DEPLOY / ".env.example"),
        dest / "setup.sh": content(DEPLOY / "setup.sh"),
        dest / "app" / "Dockerfile": content(DEPLOY / "Dockerfile"),
        dest / "app" / "entrypoint.sh": content(DEPLOY / "entrypoint.sh"),
        dest / "app" / "serve.json": content(TAILSCALE / "serve.json"),
        dest / "app" / "TAILSCALE-LICENSE": content(TAILSCALE / "TAILSCALE-LICENSE"),
        dest / "app" / "VERSION": version().encode(),
    }
    for rel in tracked(SOURCES):
        want[dest / "app" / rel] = ROOT / rel
    app = dest / "app"
    stale = [p for p in app.rglob("*") if p.is_file() and p not in want] if app.is_dir() else []
    # what this tool itself used to write beside app/, under a name it no longer uses:
    # left there, Compose would read the old file instead of the new one
    stale += [dest / name for name in RETIRED if (dest / name).is_file()]
    return want, stale


def differs(target: Path, source: bytes | Path) -> bool:
    if not target.is_file():
        return True
    if isinstance(source, bytes):
        return target.read_bytes() != source
    return (target.stat().st_size != source.stat().st_size
            or target.read_bytes() != source.read_bytes())


def seed(dest: Path, data: Path, check: bool) -> int:
    """A first copy of the data: the database as one consistent file, the crops, the catalogue."""
    target = dest / "seed-data"
    db = data / "wuwa.sqlite"
    if not db.is_file():
        print(f"no database at {db}: nothing to start the home from")
        return 1
    if target.exists() and any(target.iterdir()):
        print(f"{target} is already there. The data is copied once: if the home has started, it")
        print("holds the newer copy now. To copy again anyway, delete that folder first.")
        return 1
    files = [p for part in SEED for p in (data / part).rglob("*") if p.is_file()
             and not any(x.startswith(".") for x in p.relative_to(data).parts)]
    size = (db.stat().st_size + sum(p.stat().st_size for p in files)) / 1e6
    print(f"seed-data: the database and {len(files)} files, {size:.0f} MB")
    if check:
        return 0
    target.mkdir(parents=True, exist_ok=True)
    source, copy = sqlite3.connect(db), sqlite3.connect(target / "wuwa.sqlite")
    try:
        source.backup(copy)             # a whole, consistent database even if the app is open
    finally:
        copy.close()
        source.close()
    for path in files:
        out = target / path.relative_to(data)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, out)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("folder", type=Path, help="a folder the NAS can see")
    parser.add_argument("--seed", action="store_true", help="also copy the data, once")
    parser.add_argument("--check", action="store_true", help="say what would change; write nothing")
    parser.add_argument("--data", type=Path, default=ROOT / "data", help="where this PC's data is")
    args = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    dest = args.folder.resolve()
    if dest == ROOT or ROOT in dest.parents:
        print("not inside the repository: give a folder the NAS can see")
        return 2

    want, stale = plan(dest)
    changed = [t for t, s in want.items() if differs(t, s)]
    print(f"{dest}")
    print(f"  app: {len(want)} files; {len(changed)} to write, {len(stale)} to remove"
          + ("" if changed or stale else " -- already up to date"))
    for path in [*changed[:12], *stale[:6]]:
        print(f"    {'-' if path in stale else '+'} {path.relative_to(dest).as_posix()}")
    if len(changed) > 12:
        print(f"    … and {len(changed) - 12} more")
    if not args.check:
        for target in changed:
            source = want[target]
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(source, bytes):
                target.write_bytes(source)
            else:
                shutil.copyfile(source, target)
        for path in stale:
            path.unlink()
        for folder in sorted((p for p in (dest / "app").rglob("*") if p.is_dir()), reverse=True):
            if not any(folder.iterdir()):
                folder.rmdir()
    code = seed(dest, args.data.resolve(), args.check) if args.seed else 0
    if not args.check and code == 0:
        print("done. On the NAS, in that folder:  sh setup.sh   (docs/nas.md)")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
