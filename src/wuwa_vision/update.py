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

from .catalogue import CATALOGUE_DIR

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
#: Rebuilding the recognition gallery needs the GPU for a few minutes: opt-in.
SEED_LABEL = "识别图库"
MAX_LOG_LINES = 400


def snapshot(directory: Path | None = None) -> dict[str, set[str]]:
    """Names per kind, to tell what an update added."""
    root = Path(directory or CATALOGUE_DIR)

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
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def as_dict(self) -> dict:
        with self._lock:
            return {"state": self.state, "step": self.step, "log": self.log[-MAX_LOG_LINES:],
                    "added": self.added, "started_at": self.started_at,
                    "finished_at": self.finished_at, "seed": self.seed,
                    "can_seed": can_seed()}

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
        threading.Thread(target=self._run, daemon=True, name="catalogue-update").start()
        return True

    def _run(self) -> None:
        before = snapshot()
        steps = [(label, [sys.executable, "-u", str(TOOLS / tool), *args])
                 for label, tool, args in STEPS]
        if self.seed and can_seed():
            steps.append((SEED_LABEL, [sys.executable, "-u", "-m", "wuwa_vision", "seed"]))
        ok = TOOLS.is_dir()
        if not ok:
            self._say(f"找不到 {TOOLS}：更新只能在源码目录里运行。")
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
        for label, command in steps if ok else []:
            with self._lock:
                self.step = label
            self._say(f"== {label} ==")
            process = subprocess.Popen(
                command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            assert process.stdout is not None
            for line in process.stdout:
                self._say(line)
            if process.wait() != 0:
                self._say(f"{label}：有条目失败（见上），其余已保存。再点一次更新会只重试失败的。")
                ok = False
        after = snapshot()
        with self._lock:
            self.added = {k: sorted(after[k] - before.get(k, set())) for k in after
                          if after[k] - before.get(k, set())}
            self.state = "done" if ok else "failed"
            self.step = ""
            self.finished_at = time.time()
