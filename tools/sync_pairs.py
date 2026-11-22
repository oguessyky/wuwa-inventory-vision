# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Which scanner versions really sync with which server versions: every pair, run for real.

    uv run python tools/sync_pairs.py OUT                every released scanner x every server
    uv run python tools/sync_pairs.py OUT --with HEAD    this tree against every release, both ways

Each version's `src/` is taken from its git tag (`git archive`, nothing checked out) into OUT;
each pair gets a fresh scanner database and a fresh server database, seeded with that version's
own store, and the scanner pushes to the server and pulls from it over a real connection on
127.0.0.1 -- nothing leaves this machine, nothing of `data/` is read or written. A pair passes
only when push and pull both finish and every row either side sent arrives (`losses`).

`sync.PROTOCOL` stayed 1 from 1.0.0 on, through changes that may have broken old pairs: this is
what says which ones did, and, before each release, whether the new version breaks any.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import socket
import subprocess
import sys
import tarfile
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIDE = Path(__file__).with_name("sync_pair_side.py")
KEY = "the-key-of-this-server"
#: What a scanner sends, and what it is sent back.
PUSHED = ("scans", "gallery", "faces", "weapon_kinds", "wallet", "aliases", "character_reads",
          "icons")
PULLED = ("gallery", "faces", "weapon_kinds", "aliases", "pulls", "icons")


def versions(listed: list[str], tags: set[str]) -> list[str]:
    """The releases (`releases.json`, newest first) that have their tag, oldest first."""
    return [v for v in reversed(listed) if f"v{v}" in tags]


def losses(sent: dict, held: dict) -> list[str]:
    """Each row of `sent` that `held` does not have, in words. Empty when nothing was lost."""
    out: list[str] = []
    for kind, rows in sent.items():
        if not rows:
            continue
        if kind not in held:
            out.append(f"{kind}: {len(rows)} sent, none kept (this side has nowhere to keep them)")
            continue
        there = held[kind]
        if kind == "scans":
            for uid, n in rows.items():
                if uid not in there:
                    out.append(f"scans: {uid} did not arrive")
                elif there[uid] < n:
                    out.append(f"scans: {uid} has {n} rows, {there[uid]} arrived")
        elif isinstance(rows, dict):
            for key, value in rows.items():
                if key not in there:
                    out.append(f"{kind}: {key} did not arrive")
                elif value is not None and there[key] != value:
                    out.append(f"{kind}: {key} arrived without its name {value}"
                               if there[key] is None else
                               f"{kind}: {key} arrived as {there[key]}, not {value}")
        else:
            left = list(there)
            for row in rows:
                if row in left:
                    left.remove(row)
                else:
                    out.append(f"{kind}: {row} did not arrive")
    return out


def _side(src: Path, *args: str, cwd: Path) -> str:
    done = subprocess.run(
        [sys.executable, "-X", "utf8", str(SIDE), str(src), *args], cwd=cwd,
        capture_output=True, text=True, encoding="utf-8", timeout=600, env=_env())
    if done.returncode != 0:
        raise RuntimeError(f"{args[0]} failed ({src}):\n{done.stderr[-2000:]}")
    return done.stdout


def _env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait(url: str, server: subprocess.Popen, seconds: float = 120.0) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if server.poll() is not None:
            raise RuntimeError(f"the server stopped: {server.stderr.read()[-2000:]}")  # type: ignore[union-attr]
        try:
            with urllib.request.urlopen(f"{url}/api/sync/hello", timeout=2):  # noqa: S310 -- 127.0.0.1
                return
        except OSError:
            time.sleep(0.3)
    raise RuntimeError("the server did not answer")


def run_pair(scanner_src: Path, server_src: Path, work: Path) -> dict:
    """One scanner version against one server version, each from its own `src/`."""
    scanner, server = work / "scanner", work / "server"
    for d in (scanner, server, work / "catalogue"):
        d.mkdir(parents=True, exist_ok=True)
    s_db, h_db = scanner / "wuwa.sqlite", server / "wuwa.sqlite"
    _side(scanner_src, "seed-scanner", str(s_db), cwd=scanner)
    _side(server_src, "seed-server", str(h_db), cwd=server)
    sent = json.loads(_side(scanner_src, "dump", str(s_db), cwd=scanner))
    offered = json.loads(_side(server_src, "dump", str(h_db), cwd=server))

    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    proc = subprocess.Popen(
        [sys.executable, "-X", "utf8", str(SIDE), str(server_src), "serve", str(h_db), str(port),
         KEY], cwd=server, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
        encoding="utf-8", env=_env())
    try:
        _wait(url, proc)
        said = json.loads(_side(scanner_src, "sync", str(s_db), url, KEY,
                                str(work / "catalogue"), cwd=scanner).strip().splitlines()[-1])
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()

    held = json.loads(_side(server_src, "dump", str(h_db), cwd=server))
    took = json.loads(_side(scanner_src, "dump", str(s_db), cwd=scanner))
    pushed = {k: sent[k] for k in PUSHED if k in sent}
    pulled = {k: v for k, v in offered.items() if k in PULLED}
    lost = ([f"push: {line}" for line in losses(pushed, held)]
            + [f"pull: {line}" for line in losses(pulled, took)])
    return {"push": said.get("push"), "pull": said.get("pull"), "lost": lost,
            "sent": sorted(k for k, v in pushed.items() if v),
            "pulled": sorted(k for k, v in pulled.items() if v),
            "ok": said.get("push") == "ok" and said.get("pull") == "ok" and not lost}


def _tags() -> set[str]:
    return set(subprocess.run(["git", "tag"], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.split())


def source(version: str, out: Path) -> Path:
    """That version's `src/`, from its tag ("HEAD": this tree's own)."""
    if version == "HEAD":
        return ROOT / "src"
    dest = out / "src" / version
    if not (dest / "src").is_dir():
        tar = subprocess.run(["git", "archive", "--format=tar", f"v{version}", "src"], cwd=ROOT,
                             capture_output=True, check=True).stdout
        dest.mkdir(parents=True, exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(tar)) as t:
            t.extractall(dest, filter="data")
    return dest / "src"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("out", type=Path, help="a scratch folder for the sources and databases")
    ap.add_argument("--with", dest="only", help="only the pairs that have this version (or HEAD)")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    listed = [r["version"] for r in json.loads(
        (ROOT / "src" / "wuwa_vision" / "releases.json").read_text("utf-8"))["releases"]]
    every = versions(listed, _tags())
    if args.only:
        every = every + ["HEAD"] if args.only == "HEAD" else every
        pairs = sorted({(a, b) for a in every for b in every if args.only in (a, b)})
    else:
        pairs = [(a, b) for a in every for b in every]
    sources = {v: source(v, args.out) for v in {v for p in pairs for v in p}}

    def one(pair: tuple[str, str]) -> tuple[str, str, dict]:
        a, b = pair
        try:
            got = run_pair(sources[a], sources[b], args.out / "pairs" / f"{a}__{b}")
        except Exception as exc:  # noqa: BLE001 -- a pair that cannot be run is its result
            got = {"push": None, "pull": None, "lost": [], "ok": False, "error": str(exc)}
        print(f"scanner {a:>6}  server {b:>6}  {'ok' if got['ok'] else 'FAIL'}", flush=True)
        return a, b, got

    with ThreadPoolExecutor(args.workers) as pool:
        results = list(pool.map(one, pairs))
    (args.out / "pairs.json").write_text(json.dumps(
        [{"scanner": a, "server": b, **r} for a, b, r in results], ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"{sum(r['ok'] for _, _, r in results)} of {len(results)} pairs sync; "
          f"{args.out / 'pairs.json'}")


if __name__ == "__main__":
    main()
