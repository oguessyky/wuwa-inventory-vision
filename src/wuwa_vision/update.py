# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""The user-clicked catalogue update (D46).

The only outbound requests the main app ever makes, and only when the user clicks
更新 on the 更新 page: it runs the setup tools one after another -- fetch_catalogue
(new items and icons), fetch_recipes (dishes, potions, item pages), fetch_builds
(resonators, weapons) -- each incremental, as separate processes, exactly as they
run from the command line. Nothing runs on start-up or on a timer.

What changed is reported as names added, compared before and after.
Headless: the web app starts a job and polls its state.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import catalogue as catalogue_mod
from . import web_icons

#: The repository root, where tools/ lives (a source checkout).
ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
#: (label, tool, extra args) in the order they run.
STEPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("物品与图标", "fetch_catalogue.py", ()),
    ("料理与物品资料", "fetch_recipes.py", ()),
    ("共鸣者与武器", "fetch_builds.py", ()),
    ("共鸣者头像", "fetch_icons.py", ()),
    ("等级经验表", "fetch_levels.py", ()),
    ("商店货品", "fetch_shops.py", ()),
    # after the shops: their names, and the places they are in, are named too (D163)
    ("英文名", "fetch_english.py", ()),
    ("首领头像", "fetch_bosses.py", ()),
)
#: The steps as shipped: `STEPS` may be swapped in tests, these stay (D192).
STEPS_REAL = STEPS
#: About how long each step takes, in seconds, when nothing is there yet (a new home's first
#: download, D192) and when only what is new is fetched. A guess until a download has run here:
#: then the times it took are kept (`TIMES_NAME`) and those are the estimate.
FIRST_SECONDS: dict[str, float] = {
    "物品与图标": 120, "料理与物品资料": 150, "共鸣者与武器": 240, "共鸣者头像": 30,
    "等级经验表": 10, "商店货品": 90, "英文名": 45, "首领头像": 20,
}
LATER_SECONDS: dict[str, float] = {
    "物品与图标": 20, "料理与物品资料": 25, "共鸣者与武器": 40, "共鸣者头像": 10,
    "等级经验表": 10, "商店货品": 60, "英文名": 30, "首领头像": 10,
}
#: Beside the catalogue: how long each step took, the first time and since.
TIMES_NAME = "update-times.json"
#: A first download tries a failed step again by itself, this many times (D192): a wiki that
#: did not answer in time (`FAILED 折枝: no answer in 30s`) usually does on the next try, and
#: the tools fetch only what is still missing.
RETRIES = 2
RETRY_WAIT = 5.0
#: Rebuilding the recognition gallery needs the GPU for a few minutes: opt-in.
SEED_LABEL = "识别图库"
MAX_LOG_LINES = 400


def _catalogue_dir() -> Path:
    """Asked at each use (D188): the folder may be set up after the app started."""
    return Path(catalogue_mod.CATALOGUE_DIR)


def needs_catalogue() -> bool:
    """A new home: no catalogue yet, so no names, pictures, recipes or builds (D192)."""
    return not (_catalogue_dir() / "index.json").exists()


def _times() -> dict[str, dict[str, float]]:
    path = _catalogue_dir().parent / TIMES_NAME
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _expected(label: str, first: bool) -> float:
    kept = _times().get("first" if first else "later", {})
    if label in kept:
        return float(kept[label])
    return (FIRST_SECONDS if first else LATER_SECONDS).get(label, 30.0)


def snapshot(directory: Path | None = None) -> dict[str, set[str]]:
    """Names per kind, to tell what an update added."""
    root = Path(directory or _catalogue_dir())

    def load(name: str) -> object:
        path = root / name
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    index = load("index.json") or []
    recipes = load("recipes.json") or {}
    builds = load("builds.json") or {}
    return {
        "items": {e["name"] for e in index if e.get("tab") != "武器"},
        "weapons": set(builds.get("weapons") or {}) | {e["name"] for e in index
                                                           if e.get("tab") == "武器"},
        "resonators": set(builds.get("resonators") or {}),
        "dishes": {e["name"] for e in recipes.get("items", [])},
        "recipes": {e["name"] for e in recipes.get("recipes", [])},
    }


def can_seed() -> bool:
    """Is there a recogniser on this machine to rebuild the gallery with? A home
    that only shows the dashboard has none (D145): its scanners embed the new
    reference icons themselves, after they fetch the catalogue."""
    from importlib.util import find_spec

    return find_spec("torch") is not None and find_spec("transformers") is not None


@dataclass
class UpdateJob:
    seed: bool = False
    state: str = "idle"
    """idle | running | done | failed"""
    step: str = ""
    log: list[str] = field(default_factory=list)
    added: dict[str, list[str]] = field(default_factory=dict)
    started_at: float | None = None
    finished_at: float | None = None
    first: bool | None = None
    """This run began with no catalogue (D192): it retries what fails, and says it is the first."""
    step_no: int = 0
    step_started: float | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def as_dict(self) -> dict:
        labels = [label for label, _tool, _args in STEPS]
        with self._lock:
            first = self.first if self.first is not None else needs_catalogue()
            expected = [_expected(label, first) for label in labels]
            now = time.time()
            if self.state == "running":
                in_step = now - (self.step_started or now)
                left = sum(expected[self.step_no + 1:]) + max(
                    expected[self.step_no] - in_step if self.step_no < len(expected) else 0, 0)
            else:
                left = 0.0 if self.state in ("done", "failed") else sum(expected)
            return {"state": self.state, "step": self.step, "log": self.log[-MAX_LOG_LINES:],
                    "added": self.added, "started_at": self.started_at,
                    "finished_at": self.finished_at, "seed": self.seed,
                    "can_seed": can_seed(),
                    # how far, and how long (D192)
                    "needs_catalogue": needs_catalogue(), "first": first, "steps": labels,
                    "step_no": self.step_no, "estimate_s": round(sum(expected)),
                    "remaining_s": round(left),
                    "elapsed_s": round(now - self.started_at) if self.started_at else 0}

    def _say(self, line: str) -> None:
        with self._lock:
            self.log.append(line.rstrip())
            del self.log[:-MAX_LOG_LINES]

    def start(self) -> bool:
        """Run in a background thread. False when one is already running."""
        with self._lock:
            if self.state == "running":
                return False
            self.state, self.log, self.added = "running", [], {}
            self.started_at, self.finished_at = time.time(), None
            self.first, self.step_no, self.step_started = needs_catalogue(), 0, None
        threading.Thread(target=self._run, daemon=True, name="catalogue-update").start()
        return True

    def _run(self) -> None:
        if self.first is None:
            self.first = needs_catalogue()
        if self.started_at is None:
            self.started_at = time.time()
        before = snapshot()
        steps = [(label, [sys.executable, "-u", str(TOOLS / tool), *args])
                 for label, tool, args in STEPS]
        if self.seed and can_seed():
            steps.append((SEED_LABEL, [sys.executable, "-u", "-m", "wuwa_vision", "seed"]))
        ok = TOOLS.is_dir()
        if not ok:
            self._say(f"找不到 {TOOLS}：更新只能在源码目录里运行。")
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
        took: dict[str, float] = {}
        for number, (label, command) in enumerate(steps if ok else []):
            with self._lock:
                self.step, self.step_no, self.step_started = label, number, time.time()
            tries = 1 + (RETRIES if self.first else 0)
            for attempt in range(tries):
                if attempt:
                    self._say(f"== {label}（自动重试第 {attempt} 次）==")
                    time.sleep(RETRY_WAIT)
                else:
                    self._say(f"== {label} ==")
                if self._step(command, env) == 0:
                    break
            else:
                self._say(f"{label}：有条目失败（见上），其余已保存。再点一次更新会只重试失败的。")
                ok = False
            took[label] = round(time.time() - (self.step_started or time.time()), 1)
        self._keep_times(took)
        after = snapshot()
        with self._lock:
            self.added = {k: sorted(after[k] - before.get(k, set())) for k in after
                          if after[k] - before.get(k, set())}
            self.state = "done" if ok else "failed"
            self.step = ""
            self.step_no = len(steps)
            self.finished_at = time.time()
        # new or redrawn icons: the pages' WebP copies, in the background (D230). Even a run with
        # a failed step saved the rest; nothing happens where `serve` did not start them.
        web_icons.refresh()

    def _step(self, command: list[str], env: dict[str, str]) -> int:
        process = subprocess.Popen(
            command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        assert process.stdout is not None
        for line in process.stdout:
            self._say(line)
        return process.wait()

    def _keep_times(self, took: dict[str, float]) -> None:
        """How long each step took, for the next estimate (D192). Kept beside the catalogue."""
        if not took:
            return
        kind = "first" if self.first else "later"
        kept = _times()
        kept[kind] = {**kept.get(kind, {}), **took}
        path = _catalogue_dir().parent / TIMES_NAME
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(kept, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass                        # an estimate is a nicety: never a reason to fail
