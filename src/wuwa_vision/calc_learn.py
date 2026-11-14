# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""The reader, taught by the readings by hand (D317).

The game writes its passives from a few hundred sentences with the numbers changed: "施放变奏技能
时，攻击提升12%，持续10秒" on one weapon is "…提升20%…" on the next. Every sentence read by hand
(D303-D306) says what such words give. Words never read by hand that are made of the same
sentences are read as those were -- the whole passive where all of it was, else sentence by
sentence -- with their own numbers; a sentence never read is left to the reader (`calc_data`).

`holdout` measures it: each group (a weapon, a set, an echo, one resonator's buffs all together)
held out in turn and read as new, by the reader alone and by the reader taught by the rest.
Nothing of the game's words is kept: what is learned is built where the catalogue is.
"""

from __future__ import annotations

import collections
import json
import random
import re
from dataclasses import dataclass, field

_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_SENTENCE = re.compile(r"(?<=[。；;\n])")
_TAG = re.compile(r"<[^>]*>")
#: What an effect says beyond its number, compared and carried over.
FIELDS = ("stat", "kind", "skill", "effect", "element", "team", "others", "per_stack", "stacks",
          "when", "needs", "mode")


def _plain(text: str) -> str:
    return _TAG.sub("", text or "")


def template(text: str) -> str:
    """The words with each number as #."""
    return _NUMBER.sub("#", _plain(text).strip())


def numbers(text: str) -> list[float]:
    return [float(n) for n in _NUMBER.findall(_plain(text))]


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE.split(_plain(text)) if s.strip()]


def _said(effect: dict) -> dict:
    """An effect without its number: what carries over."""
    return {k: effect[k] for k in FIELDS if k in effect}


def _places(value: float, said: list[float]) -> list[tuple[int, float]]:
    """Where a number of the words gives this value: as a share (12 for 0.12) or as it is."""
    out = []
    for n, number in enumerate(said):
        for scale in (0.01, 1.0):
            if number and abs(number * scale - value) < 1e-6 * max(1.0, abs(value)):
                out.append((n, scale))
    return out


def _place(effects: list[dict], said: list[float]) -> list[tuple[int, float] | None]:
    """Each effect's number in the words, the first not yet taken; None where it is not one."""
    taken: set[int] = set()
    out: list[tuple[int, float] | None] = []
    for effect in effects:
        spot = next((p for p in _places(float(effect.get("value") or 0), said)
                     if p[0] not in taken), None)
        if spot:
            taken.add(spot[0])
        out.append(spot)
    return out


def _sentence_of(effects: list[dict], text: str) -> list[int | None]:
    """The sentence each effect's number is in, in order, a number taken once."""
    parts = sentences(text)
    offsets, at = [], 0
    for part in parts:
        offsets.append(at)
        at += len(numbers(part))
    spots = _place(effects, numbers(text))
    out: list[int | None] = []
    for spot in spots:
        if spot is None:
            out.append(None)
            continue
        out.append(max(i for i, start in enumerate(offsets) if start <= spot[0]))
    return out


def _written(said: list[dict], values: list[float]) -> list[dict]:
    out = []
    for effect in said:
        effect = dict(effect)
        n, scale = effect.pop("#"), effect.pop("scale")
        if n is None:
            out.append(effect)  # a value of its own, as it was read
            continue
        if n >= len(values):
            return []
        out.append({**effect, "value": values[n] * scale})
    return out


def _who(text: str, who: str | None) -> str:
    """The resonator's own name as a blank: 漂泊者·气动's words say 漂泊者."""
    base = (who or "").split("·")[0]
    return text.replace(base, "‹who›") if base else text


def _blanks(part: str, effects: list[dict]) -> tuple[str, list[dict]]:
    """A sentence's template with the skill names its effects are scoped to as blanks ‹a›, ‹b›,
    and the effects naming the blank: what carries to another resonator's skills."""
    names = sorted({e["skill"] for e in effects if e.get("skill") and e["skill"] in part},
                   key=len, reverse=True)
    for k, name in enumerate(names):
        part = part.replace(name, f"‹{chr(97 + k)}›")
    blank = {name: f"‹{chr(97 + k)}›" for k, name in enumerate(names)}
    return part, [{**e, "skill": blank[e["skill"]]} if e.get("skill") in blank else e
                  for e in effects]


#: The words before a skill's name that say its kind, as the readings by hand keep them apart:
#: 「重击末路见行」 is 末路见行, a heavy hit.
_KIND_BEFORE = (("共鸣回路", None), ("普攻", "basic"), ("重击", "heavy"), ("共鸣技能", "skill"),
                ("共鸣解放", "lib"), ("变奏技能", "intro"), ("延奏技能", "outro"))


def _clean(name: str) -> tuple[str, str | None]:
    """A skill's name filled into a blank, as a reading by hand writes it, and the kind its words
    before it say."""
    name = name.strip().removesuffix("的")
    kind = None
    for word, said in _KIND_BEFORE:
        if name.startswith(word):
            name, kind = name[len(word):], said or kind
    return name, kind


def _pattern(blanked: str) -> re.Pattern:
    out = re.escape(blanked)
    for k in "abcdefghij":
        blank = re.escape(f"‹{k}›")
        # the first is the name; the same name again matches it again
        out = out.replace(blank, f"(?P<b{k}>[^，,。；;：:、]+?)", 1).replace(blank, f"(?P=b{k})")
    return re.compile(out)


@dataclass
class Memory:
    """What the readings by hand say of each passive's words and of each sentence."""

    whole: dict[str, list[dict]] = field(default_factory=dict)
    by_sentence: dict[str, collections.Counter] = field(default_factory=dict)
    #: the numbers of the words each whole reading was learned from
    numbers_of: dict[str, list[float]] = field(default_factory=dict)
    #: the sentences with a skill's name as a blank, as patterns
    patterns: dict[str, re.Pattern] = field(default_factory=dict)

    def _sentence(self, part: str) -> list[dict] | None:
        """What a sentence of new words gives, as the same sentence read by hand -- with a
        resonator's own names where the one read had theirs."""
        shape = template(part)
        seen = self.by_sentence.get(shape)
        names: dict[str, str] = {}
        if not seen:
            for blanked, pattern in sorted(self.patterns.items(), key=lambda kv: -len(kv[0])):
                found = pattern.fullmatch(shape)
                # another resonator's words: only what two readings by hand or more agree on
                agreed = self.by_sentence[blanked].most_common(1)[0][1] >= 2
                if found and agreed and "#" not in "".join(found.groupdict().values()):
                    seen = self.by_sentence[blanked]
                    names = {f"‹{k[1:]}›": v for k, v in found.groupdict().items()}
                    break
        if not seen:
            return None
        said = json.loads(seen.most_common(1)[0][0])
        out = []
        for effect in said:
            if effect.get("skill") in names:
                name, kind = _clean(names[effect["skill"]])
                effect = {k: v for k, v in effect.items() if k != "skill"}
                if name:
                    effect["skill"] = name
                if kind and not effect.get("kind"):
                    effect["kind"] = kind
            out.append(effect)
        return _written(out, numbers(part))

    def learn(self, text: str, effects: list[dict], who: str | None = None) -> None:
        text = _who(_plain(text), who)
        said = numbers(text)
        spots = _place(effects, said)
        self.numbers_of[template(text)] = said
        self.whole[template(text)] = [
            {**_said(e), "#": s[0] if s else None, "scale": s[1] if s else None,
             **({} if s else {"value": e.get("value")})}
            for e, s in zip(effects, spots, strict=True)]
        parts = sentences(text)
        where = _sentence_of(effects, text)
        if any(w is None for w in where):
            return  # an effect with no number of its own in the words: only the whole carries it
        for i, part in enumerate(parts):
            mine = [e for e, w in zip(effects, where, strict=True) if w == i]
            local = _place(mine, numbers(part))
            if any(s is None for s in local):
                continue
            blanked, named = _blanks(part, mine)
            reading = json.dumps([{**_said(e), "#": s[0], "scale": s[1]}
                                  for e, s in zip(named, local, strict=True)],
                                 ensure_ascii=False, sort_keys=True)
            shape = template(blanked)
            self.by_sentence.setdefault(shape, collections.Counter())[reading] += 1
            if "‹a›" in shape:
                self.patterns.setdefault(shape, _pattern(shape))

    def read(self, text: str, reader: list[dict], who: str | None = None
             ) -> tuple[list[dict], str]:
        """The effects of words as new: read as the same words were by hand ("whole"), sentence by
        sentence where some were ("sentences"), or as the reader reads them ("reader")."""
        text = _who(_plain(text), who)
        said = self.whole.get(template(text))
        # a number read by hand that is not in the words carries only to the same words
        fixed = said is not None and any(e["#"] is None for e in said)
        if fixed and self.numbers_of.get(template(text)) != numbers(text):
            said = None
        if said is not None:
            written = _written(said, numbers(text))
            if len(written) == len(said):
                return written, "whole"
        parts = sentences(text)
        where = _sentence_of(reader, text)
        out: list[dict] = []
        known = False
        for i, part in enumerate(parts):
            read = self._sentence(part)
            if read is not None:
                known = True
                out += read
            else:
                out += [dict(e) for e, w in zip(reader, where, strict=True) if w == i]
        out += [dict(e) for e, w in zip(reader, where, strict=True) if w is None]
        return (out, "sentences") if known else ([dict(e) for e in reader], "reader")


def _canon(effect: dict) -> str:
    return json.dumps({**_said(effect), "value": round(float(effect.get("value") or 0), 4)},
                      ensure_ascii=False, sort_keys=True)


def score(said: list[dict], true: list[dict]) -> dict:
    """How a reading matches the one by hand: all of it, and effect by effect."""
    a = collections.Counter(_canon(e) for e in said)
    b = collections.Counter(_canon(e) for e in true)
    return {"exact": a == b, "hit": sum((a & b).values()), "said": sum(a.values()),
            "true": sum(b.values())}


@dataclass
class Item:
    """One passive read by hand: its kind, its group (held out together), its words, what the
    reader read and what the hand did."""

    kind: str
    group: str
    name: str
    text: str
    reader: list[dict]
    hand: list[dict]


def items(raw: dict, judged: dict) -> list[Item]:
    """Every passive read by hand whose words are still the ones it was read from, with what the
    reader reads in calc.json as built (`raw`, before `calc_data.judge`): a weapon at rank 1, a
    set's pieces, a main echo, each resonator's buffs and gifts."""
    from .calc_data import _number, words_key

    out: list[Item] = []
    for name, entry in (judged.get("weapons") or {}).items():
        arm = (raw.get("weapons") or {}).get(name)
        if not arm or entry["key"] != words_key(arm.get("text") or "") or not arm.get("buffs"):
            continue
        rank = arm["buffs"][0]
        params = arm.get("params") or []
        hand = [{**{k: v for k, v in e.items() if k not in ("param", "scale")},
                 "value": e["value"] if "value" in e
                 else _number(params[e["param"]][0]) * float(e.get("scale", 1))}
                for e in entry["effects"]]
        out.append(Item("weapon", f"weapon:{name}", name, rank["text"], rank.get("effects") or [],
                        hand))
    for name, read in (judged.get("sets") or {}).items():
        entry = (raw.get("sets") or {}).get(name) or {}
        for pieces, mine in read.items():
            words = (entry.get("text") or {}).get(pieces)
            if words and mine["key"] == words_key(words):
                out.append(Item("set", f"set:{name}", f"{name} {pieces}", words,
                                (entry.get("buffs") or {}).get(pieces) or [], mine["effects"]))
    for name, mine in (judged.get("echoes") or {}).items():
        main = ((raw.get("echoes") or {}).get(name) or {}).get("main_buff") or {}
        if main.get("text") and mine["key"] == words_key(main["text"]):
            out.append(Item("echo", f"echo:{name}", name, main["text"], main.get("effects") or [],
                            mine["effects"]))
    for name, read in (judged.get("roles") or {}).items():
        role = (raw.get("roles") or {}).get(name) or {}
        for buff in [*(role.get("buffs") or []), *(role.get("gives") or [])]:
            key = words_key(buff.get("text") or "")
            mine = next((o for o in read.get(buff["id"]) or [] if o["key"] == key), None)
            if mine is not None:
                out.append(Item("role", f"role:{name}", f"{name} {buff['id']}", buff["text"],
                                buff.get("effects") or [], mine["effects"]))
    return out


def _tally(rows: list[dict]) -> dict:
    hit = sum(r["hit"] for r in rows)
    said = sum(r["said"] for r in rows)
    true = sum(r["true"] for r in rows)
    return {"items": len(rows), "exact": sum(r["exact"] for r in rows),
            "precision": hit / said if said else 1.0, "recall": hit / true if true else 1.0}


def _who_of(item: Item) -> str | None:
    return item.group.split(":", 1)[1] if item.kind == "role" else None


def holdout(items: list[Item], folds: int = 5, seed: int = 0) -> dict:
    """Each group held out once, read as new by the reader and by the reader taught by the rest;
    tallied by kind, and over the items the reader alone got wrong ("corrected")."""
    groups = sorted({i.group for i in items})
    random.Random(seed).shuffle(groups)
    fold_of = {g: n % folds for n, g in enumerate(groups)}
    rows: dict[str, dict[str, list]] = {"reader": collections.defaultdict(list),
                                        "learned": collections.defaultdict(list)}
    hows: collections.Counter = collections.Counter()
    for fold in range(folds):
        memory = Memory()
        for item in items:
            if fold_of[item.group] != fold:
                memory.learn(item.text, item.hand, _who_of(item))
        for item in items:
            if fold_of[item.group] != fold:
                continue
            plain = score(item.reader, item.hand)
            effects, how = memory.read(item.text, item.reader, _who_of(item))
            hows[how] += 1
            taught = score(effects, item.hand)
            for kind in (item.kind, "all", *(["corrected"] if not plain["exact"] else [])):
                rows["reader"][kind].append(plain)
                rows["learned"][kind].append(taught)
    return {side: {kind: _tally(r) for kind, r in by.items()} for side, by in rows.items()} | {
        "how": dict(hows)}
