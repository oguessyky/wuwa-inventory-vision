# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""A few of the wiki's requests at a time (PLAN.md D202).

A new home's first download asks Kuro's wiki some 1,600 times -- every icon, every item's page,
every resonator and weapon. One after another, each waited ~2.4 s on the server, and the whole
took an hour whatever the connection's speed. A few at once divide that wait; each worker still
pauses between its own requests, so the wiki sees a handful of polite clients, not a crowd.

Used by the fetch tools, which run as scripts from this folder. `WUWA_FETCH_WORKERS=1` goes
back to one at a time.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed

#: How many requests at once, unless WUWA_FETCH_WORKERS says otherwise.
WORKERS = 6
#: How a worker waits between its requests (replaced in tests).
PAUSE_SLEEP = time.sleep


def workers() -> int:
    """WUWA_FETCH_WORKERS when it is a number from 1 up, else WORKERS."""
    said = os.environ.get("WUWA_FETCH_WORKERS", "")
    return int(said) if said.isdigit() and int(said) >= 1 else WORKERS


def each[T, R](items: Iterable[T], ask: Callable[[T], R], *, at_once: int | None = None,
               pause: float = 0.0) -> Iterator[tuple[T, R | None, BaseException | None]]:
    """(item, answer, None) or (item, None, error) for every item, as each finishes.

    One item's failure is handed back, not raised: one bad page must not stop the rest.
    """
    count = at_once or workers()

    def one(item: T) -> R:
        try:
            return ask(item)
        finally:
            if pause:
                PAUSE_SLEEP(pause)

    with ThreadPoolExecutor(max_workers=count) as pool:
        futures = {pool.submit(one, item): item for item in items}
        for future in as_completed(futures):
            error = future.exception()
            yield futures[future], (None if error else future.result()), error
