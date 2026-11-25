# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""Which echo sits in which slot, from the 声骸 page's arc (D377).

The page's read keeps its five slots (`worn.slots`, the main one first), each the echo its picture
named (or none, when unsure), its cost, its +level and its set -- or empty. Nothing is kept as an
echo read that was not one: here each slot is filled from that echo's read, and a slot no read
fills is a placeholder (`unread`), what is sure of it and no stats. 计算 and the scan's page both
place echoes with this, so they agree.
"""

from __future__ import annotations

VARIANT = "异相·"


def same_echo(a: str | None, b: str | None) -> bool:
    """One echo, whatever its form: the catalogue draws a 异相 form as its plain echo."""
    if not a or not b:
        return False
    return a.removeprefix(VARIANT) == b.removeprefix(VARIANT)


def _level_fits(slot: dict, read: dict) -> bool:
    # a level the arc did not give fits any; else the same level only (D377: a read at another
    # level is another copy of the echo, or one levelled since)
    return slot.get("level") is None or read.get("level") == slot.get("level")


def place(slots: list[dict], reads: list[dict]) -> list[dict]:
    """The slots that hold an echo, in the arc's order, each filled: `read` the echo read that is
    it (`reads` newest first), or None and `unread`. A surely named slot takes its echo's newest
    read at its level; an unsure one the one read of its cost, set and level no other slot took or
    names. Reads no slot takes are not theirs any more, and are left out."""
    held = [s for s in slots if not s.get("empty")]
    out: dict[int, dict] = {}
    used: set[int] = set()
    for slot in held:
        if slot.get("echo") is None:
            continue
        found = next((i for i, r in enumerate(reads) if i not in used
                      and same_echo(r.get("name"), slot["echo"]) and _level_fits(slot, r)), None)
        if found is not None:
            used.add(found)
        out[slot["slot"]] = _filled(slot, reads[found] if found is not None else None)
    named = [s["echo"] for s in held if s.get("echo")]
    for slot in held:
        if slot.get("echo") is not None:
            continue
        fits = [i for i, r in enumerate(reads) if i not in used
                and not any(same_echo(r.get("name"), n) for n in named)
                and (slot.get("cost") is None or r.get("cost") == slot.get("cost"))
                and (slot.get("set") is None or r.get("set") == slot.get("set"))
                and _level_fits(slot, r)]
        # the same echo read twice is one: the newest of it
        names = {(reads[i].get("name") or "").removeprefix(VARIANT) for i in fits}
        found = fits[0] if len(names) == 1 else None
        if found is not None:
            used.add(found)
        out[slot["slot"]] = _filled(slot, reads[found] if found is not None else None)
    return [out[s["slot"]] for s in held]


def _filled(slot: dict, read: dict | None) -> dict:
    if read is None:
        return {"slot": slot["slot"], "echo": slot.get("echo"), "sure": bool(slot.get("sure")),
                "cost": slot.get("cost"), "level": slot.get("level"), "set": slot.get("set"),
                "read": None, "unread": True}
    return {"slot": slot["slot"], "echo": read.get("name"), "sure": True,
            "cost": read.get("cost") or slot.get("cost"),
            "level": read.get("level") if read.get("level") is not None else slot.get("level"),
            "set": read.get("set") or slot.get("set"), "read": read, "unread": False}


#: The most cost anyone wears: the game's limit on a resonator's echoes.
COST_LIMIT = 12


def slots_of(worn: dict | None) -> list[dict] | None:
    """The 声骸 page's arc as kept with its read (D377), when it can be believed (D386); else
    None, and the echoes read are placed as before the arc was read (D367). Not believed:
    - nothing on it known: no slot's picture named and no set's badge matched (the badges were
      right on every slot D377 measured): the arc was not seen;
    - more cost than anyone wears;
    - an echo in the top slot when the page's own words say 尚未装配 (no main echo).
    The read keeps what it had: this is a judgement of it, not a change to it."""
    slots = (worn or {}).get("slots")
    if not slots:
        return None
    held = [s for s in slots if not s.get("empty")]
    if held and not any(s.get("echo") or s.get("set") for s in held):
        return None
    if sum(int(s.get("cost") or 0) for s in held) > COST_LIMIT:
        return None
    says_none = "尚未装配" in str((worn or {}).get("skill") or "").replace(" ", "")
    if says_none and not slots[0].get("empty") and slots[0].get("slot") == 1:
        return None
    return slots


def main_slot_empty(slots: list[dict] | None) -> bool:
    """The arc's top slot holds nothing: no main echo fitted (D377, as D367's words say)."""
    if not slots:
        return False
    return bool(slots[0].get("empty")) and slots[0].get("slot") == 1
