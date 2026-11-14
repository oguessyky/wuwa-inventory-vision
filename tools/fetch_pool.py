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

A request that fails on the network is asked again later (D324): it goes to the back of the
queue, after everything already waiting, and the free workers go on meanwhile. Inside a worker
a tool asks once (`attempts`), so no worker sits sleeping on its own retries.
"""

from __future__ import annotations

import http.client
import os
import threading
import time
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

#: How many requests at once, unless WUWA_FETCH_WORKERS says otherwise.
WORKERS = 6
#: How many more times a request that failed on the network is asked, each time after the rest.
AGAIN = 2
#: What a failed or cut connection raises (URLError, SSL errors and timeouts are OSErrors;
#: a reply cut short mid-body is an HTTPException).
NETWORK_ERRORS: tuple[type[BaseException], ...] = (OSError, http.client.HTTPException)
#: How a worker waits between its requests (replaced in tests).
PAUSE_SLEEP = time.sleep

_here = threading.local()


def attempts(tries: int) -> int:
    """How many times a tool should ask on its own: once inside a pool's worker, where the
    pool asks again later; `tries` anywhere else."""
    return 1 if getattr(_here, "in_pool", False) else tries


def workers() -> int:
    """WUWA_FETCH_WORKERS when it is a number from 1 up, else WORKERS."""
    said = os.environ.get("WUWA_FETCH_WORKERS", "")
    return int(said) if said.isdigit() and int(said) >= 1 else WORKERS


def each[T, R](items: Iterable[T], ask: Callable[[T], R], *, at_once: int | None = None,
               pause: float = 0.0, again: int = AGAIN,
               retry_on: tuple[type[BaseException], ...] = NETWORK_ERRORS,
               ) -> Iterator[tuple[T, R | None, BaseException | None]]:
    """(item, answer, None) or (item, None, error) for every item, once, as each finishes.

    One item's failure is handed back, not raised: one bad page must not stop the rest. A
    failure of the network is first asked again, up to `again` more times, each time behind
    everything already waiting; any other error is handed back at once.
    """
    count = at_once or workers()

    def one(item: T) -> R:
        _here.in_pool = True
        try:
            return ask(item)
        finally:
            if pause:
                PAUSE_SLEEP(pause)

    with ThreadPoolExecutor(max_workers=count) as pool:
        pending = {pool.submit(one, item): (item, 0) for item in items}
        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                item, tried = pending.pop(future)
                error = future.exception()
                if error is not None and tried < again and isinstance(error, retry_on):
                    pending[pool.submit(one, item)] = (item, tried + 1)
                    continue
                yield item, (None if error else future.result()), error
