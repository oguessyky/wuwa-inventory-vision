# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Command line entry point."""

from __future__ import annotations

import argparse
import contextlib
import shutil
import subprocess
import sys
from pathlib import Path

from .capture.windows import set_dpi_awareness
from .scan.orchestrator import scan_path
from .store.db import Store

DEFAULT_DB = Path("data/wuwa.sqlite")


def _offer_cuda(assume_no: bool = False) -> None:
    """An NVIDIA card with CPU torch: offer the CUDA build before scanning (D77).

    Recognition is the only thing on the GPU, and it is ~30x faster there, so a
    machine that could use CUDA and is not doing so is worth one question. The
    install replaces torch under a process that has already imported it, so it
    cannot take effect now -- the answer is the install plus "run it again",
    never a silent swap.
    """
    import torch

    from .setup_env import MIN_NVIDIA_DRIVER, cuda_offer, old_driver, probe

    if torch.cuda.is_available():
        return
    machine = probe()
    plan = cuda_offer(machine, cuda_available=False)
    if plan is None:
        return
    card = next((g for g in machine.gpus if "nvidia" in g.lower()), "an NVIDIA card")
    print(f"\n{card} is here, but this torch ({torch.__version__}) has no CUDA:")
    print("  recognition will run on the CPU -- correct, about 30x slower.")
    if old_driver(machine.nvidia):
        print(f"  driver {machine.nvidia} is also older than "
              f"{MIN_NVIDIA_DRIVER:.0f}: update it as well,")
        print("  or the CUDA build will load and then fail on the first scan.")
    if assume_no or not sys.stdin.isatty():
        print("  to fix it: uv run python tools/setup.py\n")
        return
    try:
        answer = input("install the CUDA build of torch now? [Y/n] ").strip().lower()
    except EOFError:
        answer = "n"
    if answer not in ("", "y", "yes"):
        print("  carrying on with the CPU.\n")
        return
    uv = shutil.which("uv")
    if not uv:
        print("  uv is not installed: winget install astral-sh.uv\n")
        return
    code = subprocess.run(  # noqa: S603 -- a fixed executable, no shell
        [uv, "pip", "install", "--index-url", plan.index, "--reinstall", "torch", "torchvision"],
        check=False,
    ).returncode
    print("\ninstalled -- run the same command again to scan on the GPU.\n" if code == 0
          else "\ninstall failed; carrying on with the CPU.\n")
    raise SystemExit(0 if code == 0 else 1)


def _open_gallery(store: Store):  # noqa: ANN202 -- recognize.gallery.Gallery (lazy import)
    """The gallery, with the shipped reference pack imported on first use (D43)."""
    from .recognize.encoder import IconEncoder
    from .recognize.gallery import Gallery
    from .recognize.pack import ensure_reference

    gallery = Gallery(store, IconEncoder())
    imported = ensure_reference(store, gallery.encoder.info.key())
    if imported:
        print(f"imported the shipped gallery pack: {imported} reference items")
    return gallery


def _cmd_pack(args: argparse.Namespace) -> int:
    """Write the reference gallery to the shipped pack (assets/gallery_pack.npz)."""
    from .recognize.pack import PACK_PATH, export_pack

    store = Store(args.db)
    try:
        n = export_pack(store, Path(args.out) if args.out else PACK_PATH)
    finally:
        store.close()
    print(f"packed {n} reference items -> {args.out or PACK_PATH}")
    return 0


def _cmd_scan(args: argparse.Namespace) -> int:
    if args.identify:
        _offer_cuda()
    store = Store(args.db)
    gallery = None
    if args.identify:
        # Imported lazily: identity needs the `recognition` extra (torch).
        gallery = _open_gallery(store)
        gallery.load()
        print(f"gallery: {gallery.size} entries on {gallery.encoder.device}")

    report = scan_path(args.path, store, read_counts=not args.no_ocr, gallery=gallery)

    print(f"scan #{report.scan_id}  source={args.path}")
    print(f"  tab            : {report.tab_label or '?'}")
    print(f"  frames used    : {report.frames_used} (skipped {report.frames_skipped})")
    print(f"  tiles read     : {report.tiles}")
    print(f"  unique icons   : {report.unique}")
    print(f"  header says    : {report.header_total if report.header_total is not None else '?'}")
    print(f"  count review   : {report.needs_review}")
    if args.identify:
        print(f"  identified     : {report.identified}")
        print(f"  unnamed        : {report.unnamed}")
        print(f"  gallery added  : {report.gallery_added}")
    print(f"  complete       : {report.complete}")
    for reason in report.skipped_reasons:
        print(f"  ! {reason}")

    if not report.complete and report.header_total is not None:
        missing = report.header_total - report.unique
        print(f"  -> {missing:+d} vs the game's own count; scan is NOT complete")
    store.close()
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    store = Store(args.db)
    scan = store.latest_scan()
    if scan is None:
        print("no scans yet")
        return 1
    rows = store.unique_items(int(scan["id"]))
    print(f"scan #{scan['id']}  {scan['tab_label'] or '?'}  {len(rows)} unique items")
    print(f"{'rarity':>7} {'count':>8}  {'seen':>5}  icon_hash")
    for r in rows[: args.limit]:
        print(
            f"{r['rarity']:>7} {str(r['count'] if r['count'] is not None else '?'):>8}"
            f"  {r['seen']:>5}  {r['icon_hash'][:16]}"
        )
    store.close()
    return 0


def _reference_is_stale(db: Path | str) -> bool:
    """Does the gallery still match the catalogue on disk? (D85)

    A scan teaches the gallery its own crops, but a catalogue that grew since the
    last seed -- a new patch's items -- has reference icons nobody embedded. That
    is the only case worth spending GPU minutes on after a scan.
    """
    from .recognize.reference import REFERENCE_DIR

    folder = Path(REFERENCE_DIR)
    if not folder.exists():
        return False
    on_disk = sum(1 for p in folder.iterdir() if p.suffix.lower() in (".png", ".webp", ".jpg"))
    store = Store(db)
    try:
        embedded = store.conn.execute(
            "SELECT COUNT(*) FROM gallery WHERE tab = 'reference'"
        ).fetchone()[0]
    finally:
        store.close()
    return bool(on_disk) and on_disk != embedded


def _cmd_seed(args: argparse.Namespace) -> int:
    """Seed the gallery from canonical reference icons."""
    from .recognize.appearance import hue_signature
    from .recognize.encoder import IconEncoder
    from .recognize.gallery import Gallery
    from .recognize.reference import load_reference_icons, reference_key

    store = Store(args.db)
    try:
        icons = load_reference_icons(args.dir) if args.dir else load_reference_icons()
    except FileNotFoundError:
        # No catalogue downloaded: the shipped pack is the reference (D43).
        from .recognize.pack import PACK_PATH, import_pack

        if not PACK_PATH.exists():
            raise
        n = import_pack(store, Gallery(store, IconEncoder()).encoder.info.key())
        print(f"no catalogue downloaded; imported the shipped gallery pack: {n} items")
        store.close()
        return 0
    print(f"reference icons: {len(icons)}")

    gallery = Gallery(store, IconEncoder())
    # The reference set is replaced, not merged: English and Chinese names for one
    # icon would make every item look like two differently-named twins (D42).
    dropped = store.conn.execute("DELETE FROM gallery WHERE tab = 'reference'").rowcount
    store.conn.commit()
    if dropped:
        print(f"replaced {dropped} earlier reference entries")
    added = gallery.add(
        [i.image for i in icons],
        [reference_key(i.image, i.name) for i in icons],
        [i.rarity for i in icons],
        names=[i.name for i in icons],
        tab="reference",
        # The catalogue's own art: its hue matches the screen (113 vs 109 right on
        # real crops), unlike the wuwatracker renders D30 left ungated.
        colours=[hue_signature(i.image) for i in icons],
    )
    # Names learned from panel reads before the catalogue existed carry OCR slips
    # (改造环 for 改造镣环). Next to the real name they would look like twins, so
    # snap them now; the alias also fixes every later read of the slip (D40/D42).
    from .recognize.names import catalogue_names, snap

    known = catalogue_names()
    learned = [r[0] for r in store.conn.execute(
        "SELECT DISTINCT item_name FROM gallery WHERE tab != 'reference' AND item_name IS NOT NULL"
    )]
    for name in learned:
        fixed = snap(name, known)
        if fixed != name:
            store.add_alias(name, fixed)
            print(f"  learned name {name} -> {fixed}")
    total = gallery.load()
    print(f"added {added}; gallery now holds {total} entries on {gallery.encoder.device}")
    store.close()
    return 0


def _cmd_windows(args: argparse.Namespace) -> int:
    """List windows and report what the guard sees.

    A diagnostic, so it reports the two halves of the guard separately. Run from a
    terminal the foreground half can never pass -- the terminal IS the foreground
    window -- and printing that as a refusal taught the wrong lesson. What this
    command is for is whether the game window is present, process-verified and
    capturable at all.
    """
    from .capture.desktop import (
        WindowGuardError,
        is_game_foreground,
        list_windows,
        require_window,
    )

    for window in list_windows():
        mark = "GAME" if window.is_game else "    "
        size = f"{window.size[0]}x{window.size[1]}"
        print(f"  {mark} {window.process:<30} {size:>12}  {window.title[:50]}")
    print()
    try:
        window = require_window(must_be_foreground=False)
    except WindowGuardError as exc:
        print(f"guard: REFUSED -- {exc}")
        return 1

    print(f"guard: window OK -- {window.title.strip()} ({window.size[0]}x{window.size[1]})")
    if is_game_foreground(window):
        print("guard: foreground OK -- capture would start immediately")
    else:
        print("guard: not foreground -- expected from a terminal;")
        print("       `wuwa live` waits for you to alt-tab in before it reads anything")
    return 0


def _cmd_platform(args: argparse.Namespace) -> int:  # noqa: ARG001
    """Which OS this is, how `wuwa live` scans on it, and whether it is ready (D152)."""
    import platform

    from .capture.desktop import scan_plan

    plan = scan_plan()
    # mac_ver is the macOS version; release() there is the Darwin kernel's.
    version = platform.mac_ver()[0] or platform.release()
    print(f"this machine: {plan.system} {version} ({platform.machine()})")
    print()
    print("how `wuwa live` scans here:")
    rows = [("frames", plan.frames)]
    if plan.supported:
        rows += [
            ("the game", plan.finds_game),
            ("to start", plan.to_front),
            ("", f"({plan.front_note})" if plan.front_note else ""),
            ("to stop", plan.stop),
            ("needs", plan.permission or "nothing to allow first"),
        ]
    for label, text in rows:
        if text:
            print(f"  {label:<9}{':' if label else ' '} {text}")
    print()
    if not plan.supported:
        print("`wuwa scan <path>` still reads saved frames here.")
        return 1

    from .capture.desktop import WindowGuardError, is_game_foreground, require_window

    try:
        window = require_window(must_be_foreground=False)
    except WindowGuardError as exc:
        print(f"game window: not ready -- {exc}")
        return 1
    print(f"game window: {window.title.strip()} ({window.size[0]}x{window.size[1]})")
    if is_game_foreground(window):
        print("in front   : yes -- `wuwa live` would start capturing at once")
    else:
        print(f"in front   : no -- expected from a terminal; `wuwa live` waits for you to "
              f"{plan.to_front}")
    return 0


def _cmd_live(args: argparse.Namespace) -> int:
    if args.share and not args.web:
        print("--share gives your phone the scan's status page: it cannot go with --no-web")
        return 2
    # Whatever the scan started beside itself ends with it, however it ends (D153).
    with contextlib.ExitStack() as ending:
        return _live(args, ending)


def _live(args: argparse.Namespace, ending: contextlib.ExitStack) -> int:
    """Capture the game window live, gate frames, and stitch a scan.

    Passive throughout: the user scrolls the bag by hand and this only watches.
    Nothing is read unless the game window is foreground at that moment.
    """
    from .capture.desktop import (
        WindowGuardError,
        is_game_foreground,
        live_capture,
        require_window,
        scan_plan,
        wait_for_foreground,
    )
    from .capture.gating import FrameGate
    from .safety.panic import PanicKeyError, panic_key
    from .scan.live_state import LiveState
    from .scan.orchestrator import DEFAULT_SKIP_TABS, run_live_scan

    # Presence is checked now, so an absent game fails in a second rather than
    # after a torch import. Foreground is checked further down, once everything
    # else is ready -- right now the foreground window is necessarily this shell.
    try:
        window = require_window(must_be_foreground=False)
    except WindowGuardError as exc:
        print(f"refusing to capture: {exc}")
        return 1

    if args.identify:
        _offer_cuda()

    panic = panic_key(args.panic_key)
    try:
        panic.arm()
    except PanicKeyError as exc:
        # Fail closed: without a way to stop, do not start. Refusing is right;
        # refusing without saying which keys ARE free just moves the guesswork
        # onto the user. (F12, the old default, was taken on this machine.)
        from .safety.panic import available_keys

        print(f"cannot arm panic key: {exc}")
        free = [k for k in available_keys() if k != args.panic_key.upper()]
        if free:
            print(f"free right now: {', '.join(free)} -- retry with --panic-key {free[0]}")
        return 1
    # Armed before anything is started, so disarmed whatever goes wrong after.
    ending.callback(panic.disarm)

    # The live page (D25): wucv's boxes-and-labels view, served locally instead
    # of drawn over the game. Started first, so it can be opened while waiting --
    # and before the home is asked anything, whose answer it shows arriving (D156).
    state = LiveState(picture=args.preview)
    if args.web:
        url = _start_live_server(Path(args.db), state, args.port)
        # Opened for the user (D153). It takes the front, which costs nothing:
        # the scan waits below for the game to be brought forward anyway.
        opened = args.open and _open_in_browser(url)
        print(f"live page: {url}  "
              + ("(opened in your browser)" if opened else "(open it in a browser on this PC)"))
    if args.share:
        shared = _share_with_phone(Path(args.db), state, args.share_port)
        if shared is not None:
            ending.callback(shared.stop)

    recorder = None
    if args.record:
        from .scan.recorder import RunRecorder

        recorder = RunRecorder(Path(args.db).parent / "runs")
        print(f"recording this run to {recorder.dir}  (--no-record to skip)")

    def say(message: str) -> None:
        print(message)
        state.say(message.strip())
        if recorder is not None:
            recorder.event("say", msg=message.strip())

    # A scanner with a home says where this scan is going before it starts, and
    # learns what the home knows first (D145). One on its own does neither.
    home = _home(args.db)
    if home is not None:
        say(f"home: {home.url} -- each tab goes there once it is finished, "
            "the rest when the scan ends")
        _watch_sync(home, state)
        _sync_before(args.db, home, say)
    store = Store(args.db)
    gallery = holders = None
    if args.identify:
        gallery = _open_gallery(store)
        print(f"gallery: {gallery.load()} entries on {gallery.encoder.device}")
        # The 武器 tab's portraits (D61): who is carrying which weapon. Shares the
        # encoder -- one CUDA framework in the process, and one model in VRAM.
        from .recognize.holders import Holders

        holders = Holders(store, gallery.encoder)
        faces = holders.load()
        print(
            f"holders: {faces} reference avatars"
            if faces
            else "holders: no avatars downloaded -- the 武器 tab will not say who holds what"
        )

    skip_tabs = [] if args.all_tabs else (args.skip_tab or list(DEFAULT_SKIP_TABS))
    if skip_tabs:
        print(f"skipping tabs: {', '.join(skip_tabs)}  (--all-tabs to scan everything)")

    print(f"target: {window.title.strip()} ({window.size[0]}x{window.size[1]})")
    plan = scan_plan()
    print(f"open the bag, then {plan.to_front} -- waiting up to {args.wait:.0f}s.")
    if plan.front_note:
        print(f"  ({plan.front_note})")
    print("scroll by hand; click an item to read its name and 拥有 count from the panel.")
    print(f"switch tabs freely; press {panic.key} to finish. Budget {args.seconds:.0f}s.")
    state.set_status("waiting")
    state.say("waiting for the game window")

    def countdown(remaining: float) -> None:
        print(f"\r  waiting for the game window... {remaining:5.1f}s ", end="", flush=True)

    try:
        window = wait_for_foreground(
            timeout=args.wait, on_wait=countdown, should_abort=lambda: panic.triggered
        )
    except WindowGuardError as exc:
        print(f"\ngave up: {exc}")
        panic.disarm()
        store.close()
        return 1
    print("\r" + " " * 60 + "\r", end="")
    say("  game window is foreground -- capturing.")
    state.set_status("capturing")

    def focus_changed(focused: bool) -> None:
        say("  focus regained -- resuming" if focused else "  focus lost -- paused")
        state.set_status("capturing" if focused else "paused")

    announced_complete: set[str] = set()

    def view_read(view) -> None:  # noqa: ANN001 -- orchestrator.View
        """Say what this view added, the moment it is read -- not only at the end."""
        report, stitcher = view.tab.report, view.tab.stitcher
        state.update_view(view, view.tabs)
        if recorder is not None:
            recorder.view(view)
        new = stitcher.last_new
        tab = f"[{report.tab_label}] " if report.tab_label else ""
        say(f"  {tab}view {report.frames_used}: +{len(new)} new -> {stitcher.progress()}")
        for item in new:
            print(f"      + {_describe_item(item)}")
        miss = report.panel_unmatched
        if miss is not None:
            say(f"  ~ read {miss.name} (拥有 {miss.owned}) but could not match it to the "
                "selected tile yet -- hold still, it retries")
        read = report.last_panel
        if read is not None:
            extra = f" ({read.category})" if read.category else ""
            if read.level is not None:
                # A weapon: one copy per tile, so the panel has a level and a
                # 谐振 rank where a bag item has 拥有 (D96).
                rank = f" {read.rank}阶" if read.rank is not None else ""
                say(f"      = selected: {read.name}  Lv.{read.level}{rank}{extra}")
            else:
                owned = read.owned if read.owned is not None else "?"
                say(f"      = selected: {read.name}  拥有 {owned}{extra}")
        unsure = [i for i in stitcher.items.values() if i.needs_click]
        fresh = [i for i in unsure if i in new]
        if fresh:
            say(f"  ! {len(fresh)} item(s) look identical to other items -- click each to tell "
                f"them apart: {', '.join(' / '.join(i.rivals) for i in fresh)}")
        if not stitcher.last_registered and not stitcher.complete:
            say("  ! this view shares no row with anything seen so far -- rows in between")
            say("    may be missing. Scroll back up until the previous items show again.")
        if report.frames_used == 1 and new and stitcher.named == 0:
            say("  ! nothing here matched a named icon. Click an item and its Chinese name")
            say("    and 拥有 count are read from the panel on the right -- and remembered.")
        label = report.tab_label or "?"
        if stitcher.complete and label not in announced_complete:
            announced_complete.add(label)
            say(f"  == {label} complete: all {stitcher.header_total} items seen.")
            say(f"     Switch tab to keep going, or press {panic.key} to finish.")

    def phase_changed(phase: str) -> None:
        # Shown on the live page, which is where the user looks between clicks.
        # Not printed: a status line would interleave with the per-view lines.
        state.set_phase(phase)
        if recorder is not None:
            recorder.event("phase", phase=phase)

    def gate_event(kind: str, data: dict) -> None:
        if recorder is not None:
            recorder.event(kind, **data)

    def tab_skipped(label: str) -> None:
        say(f"  -> tab {label}: skipped, nothing here is read or saved")

    def tab_changed(tab) -> None:  # noqa: ANN001 -- TabScan
        total = tab.report.header_total
        say(f"  -> tab {tab.label}" + (f" (game says {total} items)" if total else ""))

    capture = live_capture(window)
    gate = FrameGate.live()
    # a tab finished during the scan goes home then, in the background (D173)
    early = None
    if home is not None:
        from . import sync as _sync

        early = _sync.EarlyPush(lambda: home, args.db, say)
    try:
        result = run_live_scan(
            capture.frames(timeout=args.seconds),
            store,
            source=window.title,
            gallery=gallery,
            holders=holders,
            gate=gate,
            panic=panic,
            max_seconds=args.seconds,
            # Several tabs per session: a finished tab is announced, not an exit.
            stop_when_complete=False,
            focus_ok=lambda: is_game_foreground(window),
            focus_grace=args.focus_grace,
            on_focus_change=focus_changed,
            on_view=view_read,
            on_tab=tab_changed,
            on_tab_closed=early.send if early is not None else None,
            skip_tabs=skip_tabs,
            on_skip=tab_skipped,
            on_phase=phase_changed,
            on_frame=(lambda f: state.offer_preview(f.rgb)) if args.web and args.preview else None,
            on_event=gate_event,
        )
    finally:
        capture.stop()
        panic.disarm()
        if recorder is not None:
            recorder.close()
    state.update_tabs(result.tabs)
    state.set_status("stopped")

    print()
    reason = result.stop_reason
    if result.aborted:
        reason = f"{panic.key} pressed -- everything read so far is saved"
    print(f"stopped: {reason}")
    unfocused = sum(t.report.frames_unfocused for t in result.tabs)
    # Views, not gate accepts: a click is read too, and the gate never sees it
    # as a new frame -- "46 read" stood beside 62 reported views (D96).
    views = sum(t.report.frames_used for t in result.tabs)
    print(f"  frames : {gate.stats.seen} seen, {views} read "
          f"({gate.stats.accepted} after a scroll, {gate.stats.moving} moving, "
          f"{gate.stats.repeat} repeat, {unfocused} unfocused)")

    for tab in result.tabs:
        report, stitcher = tab.report, tab.stitcher
        if not report.frames_used:
            continue
        print()
        print(f"[{report.tab_label or '?'}] {stitcher.progress()}  "
              f"named {stitcher.named}, from panel {report.panel_reads}, "
              f"count review {stitcher.needs_review}"
              + ("  COMPLETE" if report.complete else ""))
        if stitcher.gaps and not report.complete:
            # Not on a complete tab: the game's own count says nothing is missing.
            print(f"  ! {stitcher.gaps} view(s) did not overlap -- rows may be missing")
        if stitcher.overcount:
            print(f"  ! {stitcher.overcount} more items than the game reports: "
                  "some were counted twice")
        elif stitcher.remaining:
            print(f"  ! {stitcher.remaining} items not seen yet")
        unsure = [i for i in stitcher.items.values() if i.needs_click]
        if unsure:
            print(f"  ! {len(unsure)} item(s) still need a click to be told apart (marked ?)")
        for n, item in enumerate(stitcher.sorted_items(), 1):
            print(f"  {n:>4}. {_describe_item(item)}")
    store.close()
    if args.web:
        say(f"stopped: {reason}")
    if home is not None:
        if early is not None:
            early.wait()                    # what was being sent during the scan, first
        _sync_after(args.db, home, say)
    if args.web:
        _stay_with_the_page(state)

    # A catalogue that grew since the last seed has icons nobody embedded, and
    # the scan just proved the machine is set up to do it (D85).
    if args.identify and not args.no_seed and _reference_is_stale(args.db):
        print("\nthe catalogue grew since the gallery was built -- seeding it now")
        print("  (skip this with --no-seed)")
        _cmd_seed(argparse.Namespace(db=args.db, dir=None))
    return 0


def _serve_in_background(app, port: int, name: str) -> None:  # noqa: ANN001 -- FastAPI
    """Serve `app` from a background thread. 127.0.0.1 only, whoever it is for."""
    import threading

    import uvicorn

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, name=name, daemon=True).start()


def _start_live_server(db: Path, state, port: int) -> str:  # noqa: ANN001 -- LiveState
    """Serve the live page. 127.0.0.1 only (zero egress)."""
    from .web.app import create_app

    _serve_in_background(create_app(db, live=state), port, "live-page")
    return f"http://127.0.0.1:{port}/live"


def _open_in_browser(url: str) -> bool:
    """Show `url` in the user's own browser. False when there is none to ask."""
    import webbrowser

    with contextlib.suppress(Exception):  # no desktop, no browser: the link is printed anyway
        return webbrowser.open(url)
    return False


def _share_with_phone(db: Path, state, port: int):  # noqa: ANN001, ANN202 -- LiveState, Share
    """Give the user's phone the scan's status (D153): a second app that can only
    be read, on its own port, and that port alone handed to their tailnet.

    The share, or None having said why not -- the scan then runs as it always did.
    """
    from .web import tailnet
    from .web.app import create_phone_app

    shared, why = tailnet.open_share(port)
    if shared is None:
        print(f"phone page: not shared ({why})")
        return None
    _serve_in_background(create_phone_app(db, state), port, "phone-page")
    print(f"phone page: {shared.url}  (your own Tailscale devices only; it shows the")
    print("            scan's progress, changes nothing, and never a picture of the game)")
    return shared


def _describe_item(item) -> str:  # noqa: ANN001 -- StitchedItem; torch-free import path
    stars = f"{item.rarity}*" if item.rarity > 0 else "?*"
    if item.count is None:
        count = "x?"
    else:
        count = f"x{item.count}" + ("" if not item.needs_review else " (unsure)")
    # "=" marks name and count read from the game's own detail panel; "?" an item
    # that looks identical to others and needs a click to be told apart.
    if getattr(item, "needs_click", False):
        name = "? " + " / ".join(item.rivals) + "  -- click to tell apart"
        return f"{stars:>3} {count:<14}?{name}  {item.icon_hash[:8]}"
    mark = "=" if getattr(item, "confirmed", False) else " "
    return f"{stars:>3} {count:<14}{mark}{item.item_name or '(unnamed)'}  {item.icon_hash[:8]}"


# ------------------------------------------------------------ a scanner and its home (D145)


def _home(db: Path | str):  # noqa: ANN202 -- sync.Home | None
    """This scanner's home, if it was given one. A machine on its own has none."""
    from . import sync

    said = sync.read_home(Path(db).parent)
    return sync.Home(said["url"], said["key"]) if said else None


def _sync_before(db: Path | str, home, say=print) -> None:  # noqa: ANN001 -- sync.Home
    """Before a scan: hand over what the last one left, then learn what the home knows.

    Never stops a scan. A home that cannot be reached means this machine scans on
    what it already knows, and the scan waits here until the home answers again.
    `say` takes its lines: the terminal, and from a scan its pages too (D156).
    """
    from . import sync
    from .catalogue import CATALOGUE_DIR

    store = Store(db)
    try:
        sent = home.push(store)
        if sent.get("scans"):
            say(f"  home: sent {sent['scans']} scan(s) kept from before")
        took = home.pull(store, Path(CATALOGUE_DIR))
        if took.get("set_aside"):
            say(f"  home: its scans were wiped; this copy was set aside in {took['set_aside']}")
        learned = {k: v for k, v in took.items() if v and k != "set_aside"}
        say("  home: up to date" if not learned else
            "  home: fetched " + ", ".join(f"{v} {k}" for k, v in learned.items()))
    except sync.SyncError as exc:
        say(f"  ! home: {exc}")
        say("    scanning on this machine's copy; the scan is kept and sent next time")
    finally:
        store.close()


def _sync_after(db: Path | str, home, say=print) -> None:  # noqa: ANN001 -- sync.Home
    """After a scan: hand it over. Kept, and said so, if the home does not answer."""
    from . import sync

    store = Store(db)
    print()
    try:
        sent = home.push(store)
        waiting = len(sync.unsent_scans(store))
        say(f"home: sent {sent.get('scans', 0)} scan(s) to {home.url}"
            + (f"; {waiting} still waiting" if waiting else ""))
    except sync.SyncError as exc:
        say(f"! home: {exc}")
        say(f"  {len(sync.unsent_scans(store))} scan(s) kept here; "
            "they go with the next scan, or now with: wuwa push")
    finally:
        store.close()


def _size(count: float) -> str:
    return f"{count / 1e6:.1f} MB" if count >= 1e6 else f"{count / 1e3:.0f} KB"


def _sync_line(said: dict) -> str:
    """One half of a sync in a line (D156): a bar, what is left, how fast it goes.

    What matters most comes first: the line is cut to the terminal's width."""
    fraction = said.get("fraction")
    filled = round(20 * fraction) if fraction is not None else 0
    bar = "[" + "#" * filled + "-" * (20 - filled) + "]"
    percent = f"{100 * fraction:3.0f}%" if fraction is not None else " ..."
    parts = [f"{'to home  ' if said.get('way') == 'up' else 'from home'} {bar} {percent}"]
    step, items = said.get("step"), said.get("items") or 0
    size = said.get("bytes")
    by_bytes = (f"{_size(max(size - said['bytes_done'], 0))} left of {_size(size)}"
                if size else "")
    if step == "crops":
        parts.append(f"{items - said['items_done']} of {items} crops left")
    elif step == "catalogue":
        parts.append(f"{items - said['items_done']} of {items} files left"
                     + (f", {by_bytes}" if by_bytes else ""))
    elif step == "learned":
        parts.append("what it has learned" + (f", {by_bytes}" if by_bytes else ""))
    elif by_bytes:
        parts.append(by_bytes)
    if said.get("rate"):
        parts.append(f"{_size(said['rate'])}/s")
    holds = said.get("holds") or {}
    if step == "scans":
        parts.append(f"({holds.get('scans', 0)} scan(s), {holds.get('crops', 0)} crop(s))")
    return "  ".join(parts)


def _watch_sync(home, state=None, terminal: bool | None = None) -> None:  # noqa: ANN001
    """Show how the talk with the home is going (D156): one line here that draws
    over itself, and through `state` the live page and the phone's page.

    Nothing is drawn when this is not a terminal: a log would get a line a block."""
    drawn = 0
    if terminal is None:
        terminal = sys.stdout.isatty()

    def tell(said: dict | None) -> None:
        nonlocal drawn
        if state is not None:
            state.set_sync(said)
        if not terminal:
            return
        room = shutil.get_terminal_size().columns - 1
        text = "" if said is None else ("  " + _sync_line(said))[:room]
        print("\r" + text.ljust(drawn), end="\r" if said is None else "", flush=True)
        drawn = len(text)

    home.tell = tell


def _enter_pressed() -> bool:
    """Was Enter pressed since this last looked? It never waits: the loop that
    asks is watching the live page as well (D156)."""
    if sys.platform == "win32":
        import msvcrt

        pressed = False
        while msvcrt.kbhit():
            pressed |= msvcrt.getwch() in "\r\n"
        return pressed
    import select

    if select.select([sys.stdin], [], [], 0)[0]:
        sys.stdin.readline()
        return True
    return False


def _stay_until_left(state, pressed=_enter_pressed, pause: float = 0.2) -> str:  # noqa: ANN001
    """Wait until the live page's tab is closed ("tab") or Enter is pressed ("enter")."""
    import time

    while True:
        if pressed():
            return "enter"
        if state.page_gone():
            return "tab"
        time.sleep(pause)


def _stay_with_the_page(state) -> None:  # noqa: ANN001 -- LiveState
    """The scan is over: keep its page up for as long as it is looked at (D156).

    Closing the page's tab ends the wait; so does Enter, which is all there is
    when the page was never opened or the browser went without a word. With no
    console there is no Enter to wait for, and the command ends as it always did.
    """
    if sys.stdin is None or not sys.stdin.isatty():
        with contextlib.suppress(EOFError):  # no console attached: just exit
            input("\nthe live page stays up until you press Enter here. ")
        return
    print("\nthe live page stays up until you close its tab, or press Enter here. ",
          end="", flush=True)
    print("" if _stay_until_left(state) == "enter" else "\nlive page closed.")


def _cmd_home(args: argparse.Namespace) -> int:
    """Give this scanner a home, show it, or take it away."""
    from . import sync

    data = Path(args.db).parent
    if args.action == "forget":
        sync.write_home(data, None)
        print("this machine is on its own again: scans stay here")
        return 0
    if args.action == "set":
        if not args.url or not args.key:
            print("usage: wuwa home set http://<name>.ts.net:4000 <key>")
            print("  the key is the one line in data/home.key on the home")
            return 2
        try:
            home = sync.Home(args.url, args.key)
            said = home.check()
        except sync.SyncError as exc:
            print(f"not set: {exc}")
            return 1
        sync.write_home(data, home.url, args.key)
        # This copy joins the home as it is: what it holds is offered, not thrown
        # away. Only a wipe of the home from now on makes it start over.
        store = Store(args.db)
        store.set_setting(sync.SYNC_EPOCH, str(said["epoch"]))
        waiting = len(sync.unsent_scans(store))
        store.close()
        print(f"home: {home.url}")
        print(f"  every scan from now on is sent there; {waiting} scan(s) here go with the next "
              "one, or now with: wuwa push")
        return 0
    said = sync.read_home(data)
    if not said:
        print("no home: this machine keeps its own scans (the default)")
        print("  to send them to an always-on one: wuwa home set http://<name>.ts.net:4000 <key>")
        return 0
    store = Store(args.db)
    waiting = len(sync.unsent_scans(store))
    store.close()
    print(f"home: {said['url']}   ({waiting} scan(s) waiting to be sent)")
    return 0


def _cmd_push(args: argparse.Namespace) -> int:
    from . import sync

    home = _home(args.db)
    if home is None:
        print("no home set: wuwa home set http://<name>.ts.net:4000 <key>")
        return 1
    store = Store(args.db)
    _watch_sync(home)
    try:
        sent = home.push(store)
    except sync.SyncError as exc:
        print(f"not sent: {exc}")
        return 1
    finally:
        store.close()
    print(f"sent {sent.get('scans', 0)} scan(s) to {home.url}"
          + (f" ({sent['known']} it already had)" if sent.get("known") else ""))
    return 0


def _cmd_pull(args: argparse.Namespace) -> int:
    from . import sync
    from .catalogue import CATALOGUE_DIR

    home = _home(args.db)
    if home is None:
        print("no home set: wuwa home set http://<name>.ts.net:4000 <key>")
        return 1
    store = Store(args.db)
    _watch_sync(home)
    try:
        took = home.pull(store, Path(CATALOGUE_DIR))
    except sync.SyncError as exc:
        print(f"not fetched: {exc}")
        return 1
    finally:
        store.close()
    if took.get("set_aside"):
        print(f"the home's scans were wiped; this copy was set aside in {took['set_aside']}")
    learned = {k: v for k, v in took.items() if v and k != "set_aside"}
    print("up to date" if not learned else
          "fetched " + ", ".join(f"{v} {k}" for k, v in learned.items()))
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from .web import tailnet
    from .web.app import create_app

    # The app binds this PC only, always. Other devices reach it through
    # Tailscale's own proxy, on the user's tailnet and nowhere else (D108).
    print(f"  main app: http://127.0.0.1:{args.port}")
    key = None
    if args.home:
        # A home takes scans from scanners that show its key (D145). The key is a
        # file beside the data, never printed: whoever can read the file may upload.
        from . import sync

        key = sync.home_key(Path(args.db).parent, create=True)
        print(f"  home    : takes scans from scanners holding the key in "
              f"{Path(args.db).parent / sync.HOME_KEY_FILE}")
    else:
        # A scanner's own pages show only what this machine holds: say where the rest is.
        here = _home(args.db)
        if here is not None:
            print(f"  note    : this machine sends its scans to {here.url} -- the dashboard "
                  "with everything is there")
    shared = None if args.local else tailnet.share(args.port)
    if args.local:
        print("  tailnet : not shared (--local)")
    try:
        uvicorn.run(create_app(Path(args.db), home_key=key), host="127.0.0.1", port=args.port,
                    log_level="info")
    finally:
        if shared is not None:
            shared.stop()
    return 0


def main(argv: list[str] | None = None) -> int:
    # The Windows console defaults to cp1252, which cannot encode the CJK tab
    # labels and item names this tool exists to read.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    # Before any window query: DPI-unaware, Windows reported this machine's
    # 3440x1440 game window as 1707x1067, so every size printed was a 2x lie.
    set_dpi_awareness()
    parser = argparse.ArgumentParser(prog="wuwa", description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite path")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan", help="scan a fixture image or directory")
    p_scan.add_argument("path")
    p_scan.add_argument("--no-ocr", action="store_true", help="skip count OCR (geometry only)")
    p_scan.add_argument(
        "--identify", action="store_true",
        help="match icons against the embedding gallery (needs: uv sync --extra recognition)",
    )
    p_scan.set_defaults(func=_cmd_scan)

    p_show = sub.add_parser("show", help="print the latest scan")
    p_show.add_argument("--limit", type=int, default=40)
    p_show.set_defaults(func=_cmd_show)

    p_seed = sub.add_parser("seed", help="seed the gallery from canonical reference icons")
    p_seed.add_argument(
        "--dir", default=None,
        help="reference icon folder (default: data/catalogue, else data/reference_icons)",
    )
    p_seed.set_defaults(func=_cmd_seed)

    p_pack = sub.add_parser("pack", help="write the reference gallery to the shipped pack")
    p_pack.add_argument("--out", default=None, help="default: assets/gallery_pack.npz")
    p_pack.set_defaults(func=_cmd_pack)

    p_win = sub.add_parser("windows", help="list windows and test the capture guard")
    p_win.set_defaults(func=_cmd_windows)

    p_plat = sub.add_parser(
        "platform", help="which OS this is, how `live` scans on it, and whether it is ready",
    )
    p_plat.set_defaults(func=_cmd_platform)

    from .safety.panic import DEFAULT_KEY

    p_live = sub.add_parser("live", help="capture the game window live and scan it")
    p_live.add_argument("--seconds", type=float, default=1200.0, help="time budget")
    p_live.add_argument(
        "--panic-key", default=DEFAULT_KEY, help="hotkey that stops the scan (default F9)"
    )
    p_live.add_argument(
        "--wait", type=float, default=60.0,
        help="seconds to wait for you to alt-tab into the game before giving up",
    )
    p_live.add_argument(
        "--focus-grace", type=float, default=120.0,
        help="seconds the game may stay unfocused mid-scan before the scan stops "
             "(0 = stop the moment focus is lost)",
    )
    p_live.add_argument("--identify", action="store_true")
    p_live.add_argument(
        "--no-seed", action="store_true",
        help="do not rebuild the recognition gallery afterwards when the "
             "catalogue has grown since it was last built",
    )
    p_live.add_argument(
        "--no-web", dest="web", action="store_false",
        help="do not serve the live page on 127.0.0.1",
    )
    p_live.add_argument(
        "--preview", action="store_true",
        help="show the game's item grid under the boxes on the live page (~8 fps; "
             "costs CPU next to the game -- the default is boxes on black)",
    )
    p_live.add_argument("--port", type=int, default=8711, help="live page port")
    p_live.add_argument(
        "--no-open", dest="open", action="store_false",
        help="do not open the live page in your browser; just print its link",
    )
    p_live.add_argument(
        "--share", action="store_true",
        help="also show the scan's status on your phone: a read-only page for your own "
             "tailnet, for when this PC's one screen is the game (needs Tailscale)",
    )
    p_live.add_argument("--share-port", type=int, default=8713, help="phone page port")
    p_live.add_argument(
        "--no-record", dest="record", action="store_false",
        help="do not keep this run's views, crops and reads under data/runs/",
    )
    p_live.add_argument(
        "--skip-tab", action="append", metavar="LABEL",
        help="never scan a tab whose header contains LABEL; repeatable. "
             "Replaces the default list (声骸 echoes, 任务 quest items, "
             "特殊 special items)",
    )
    p_live.add_argument("--all-tabs", action="store_true", help="skip no tabs")
    p_live.set_defaults(func=_cmd_live)

    p_serve = sub.add_parser(
        "serve",
        help="run the main app on 127.0.0.1:4000, and share it with your own tailnet when "
             "Tailscale is connected",
    )
    p_serve.add_argument("--port", type=int, default=4000)
    p_serve.add_argument(
        "--local", action="store_true",
        help="this PC only: do not share the app with your tailnet",
    )
    p_serve.add_argument(
        "--home", action="store_true",
        help="be the home of other machines' scans: take uploads from scanners that hold "
             "the key in data/home.key (made on first start)",
    )
    p_serve.set_defaults(func=_cmd_serve)

    p_home = sub.add_parser(
        "home", help="send this machine's scans to an always-on copy of the app on your tailnet")
    p_home.add_argument("action", nargs="?", choices=["show", "set", "forget"], default="show")
    p_home.add_argument("url", nargs="?", help="the home's tailnet address")
    p_home.add_argument("key", nargs="?", help="the one line in data/home.key on the home")
    p_home.set_defaults(func=_cmd_home)
    sub.add_parser("push", help="send finished scans to the home now").set_defaults(func=_cmd_push)
    sub.add_parser(
        "pull", help="fetch what the home has learned, and its catalogue, now"
    ).set_defaults(func=_cmd_pull)

    args = parser.parse_args(argv)
    from .recognize.encoder import ModelMissingError

    try:
        return int(args.func(args))
    except ModelMissingError as exc:
        # Weights are vendored, never fetched at runtime (D41): say how to get them.
        print()
        print(exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
