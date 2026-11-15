# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
"""What a name can be typed as, besides itself (D136).

The names are Chinese. Not everyone who plays types Chinese, and not everyone
who does remembers a rare character: so a search box also takes the name in
pinyin ("jinxi"), by its initials ("jx"), and -- where one is known -- in
English ("jinhsi"). The page compares what was typed against these keys; the
name itself is still matched as written.

Pinyin is computed here (pypinyin), not looked up anywhere. Each character
takes the reading it usually has; the few that are commonly read two ways give
a key for each, so 长离 is found by "changli", which is right, and by "zhangli",
which is what a dictionary offers first.
"""

from __future__ import annotations

import re
from functools import lru_cache
from itertools import islice, product

#: Characters people really do read two ways, with the other reading. Every
#: reading a dictionary lists would be far too many: 射 has three, 朴 four, and a
#: long name would be found by spellings nobody types.
ALSO = {"长": "chang", "重": "chong", "行": "hang", "乐": "yue", "朝": "zhao", "藏": "zang",
        "传": "zhuan", "调": "diao", "降": "xiang", "角": "jue", "血": "xie", "薄": "bao",
        "还": "hai", "弹": "tan", "奇": "ji"}
#: Spellings kept per name.
MAX_SPELLINGS = 8
_CHINESE = re.compile(r"[一-鿿]+|[0-9A-Za-z]")


def _readings(name: str) -> list[list[str]]:
    """Per character, the reading it has in this name and any other common one."""
    # imported when first wanted (a fifth of a second): an English page never needs it (D327)
    from pypinyin import lazy_pinyin

    out: list[list[str]] = []
    for run in _CHINESE.findall(name):
        if not ("一" <= run[0] <= "鿿"):
            out.append([run.lower()])
            continue
        # a run at a time, so that 漂泊 is read as the word it is
        for char, usual in zip(run, lazy_pinyin(run), strict=False):
            usual = usual.replace("ü", "v")
            other = ALSO.get(char)
            out.append(list(dict.fromkeys([usual, *([other] if other else [])])))
    return out


def keys(name: str, english: str = "", lang: str | None = None) -> str:
    """Lowercase, space-separated: every pinyin spelling of `name`, each one's
    initials, and the English name as written and as letters only.

    `lang`: "zh" keeps the pinyin and initials, "en" the English alone -- the two parts of
    the search index (D327, D328). None: both, as every page's box finds by both."""
    return _keys(name, english, lang if lang in ("zh", "en") else None)


@lru_cache(maxsize=16384)
def _keys(name: str, english: str, lang: str | None) -> str:
    out: list[str] = []
    if lang != "en":
        parts = _readings(name)
        for spelling in islice(product(*parts), MAX_SPELLINGS) if parts else []:
            out.append("".join(spelling))
            out.append("".join(s[0] for s in spelling))
    said = " ".join(english.lower().split()) if lang != "zh" else ""
    if said:
        out.append(said)
        out.append("".join(c for c in said if c.isalnum()))
    return " ".join(dict.fromkeys(k for k in out if k))
