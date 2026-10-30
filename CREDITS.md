# Credits, copyright and licences

WuWa Inventory Vision is an **unofficial, fan-made tool**. It is not affiliated with, endorsed
by, sponsored by, or approved by Kuro Games.

This file says what in this repository is whose. Where it quotes someone's terms, the quote was
read from the linked page on 2026-10-10; those pages can change, and they are the authority, not
this file.

## 1. This project's own code — Apache License 2.0

The source code and documentation written for this project are released under the
[Apache License, Version 2.0](LICENSE). Copyright 2026 oguessyky; the [NOTICE](NOTICE) file carries
that line, and anyone who redistributes the project keeps it, as the licence asks.

**The Apache licence covers only that.** It does not cover, and cannot grant any right in,
anything listed in sections 2 to 4. Its patent clause is about patents of the people who
contribute code to this project; it says nothing about, and gives nothing in, anything of Kuro
Games'.

## 2. Wuthering Waves — Kuro Games

*Wuthering Waves* (鸣潮) is developed and published by Kuro Games (库洛游戏). Everything that comes
from the game — character and item names, icons, portraits, artwork, text, interface, screenshots,
logos — belongs to Kuro Games and is protected by copyright, trademark and other intellectual
property law. Nothing in this repository changes that, and no licence to any of it is given here.

What Kuro Games' own documents say:

- The game's **Terms of Use** (effective 29 September 2025) are an agreement with "HK KURO GAMES
  LIMITED with all its affiliates". Section 2, *Ownership*, claims "exclusive proprietary rights,
  all intellectual property rights and all other interests" in the services and in the content
  provided through them, naming among other things images, graphics, logos, characters, character
  names, weapons and in-game items.
  <https://wutheringwaves.kurogames.com/p/language_de/terms_of_service.html>
- The **Guidelines for Derivative Works of Wuthering Waves** are "made by Kurogame Technology
  (Guangzhou) Co., Ltd." and state that "Kurogame has the full and complete Intellectual Property
  Right with regards to Wuthering Waves". The guidelines cover fan works such as writing, images
  and video; their definition of a derivative work makes an exception of "games (material or
  digital), software and commercial works/merchandises".
  <https://wutheringwaves.kurogames.com/p/en/produce.html>

So, plainly: **this project has no licence or written permission from Kuro Games**, and Kuro's
fan-work guidelines do not extend to software. The project is built to keep Kuro's material out of
what it distributes:

- **The app ships no game images.** Icons and portraits are downloaded to the user's own computer
  (the git-ignored `data/` folder) by the user, from the sources in section 3, and are shown only
  there. They are not part of this repository or of any release of it.
- **`assets/gallery_pack.npz`** holds item names, rarities and numbers computed from the icons
  (embeddings and colour vectors) so that items can be recognised. It contains no images. The names
  in it are the game's.
- **`docs/screens/`** holds screenshots of this app, which show game icons and portraits: Kuro
  Games' material shown for documentation, not under the project's licence.

If Kuro Games asks for anything here to be changed or removed, it will be.

"Wuthering Waves", "鸣潮", "Kuro Games" and their logos are trademarks of their owner. They are
used here only to say what the tool is for.

## 3. Where the app's game data comes from

None of this is bundled. The app fetches it when the user runs setup or presses the button on the
更新 page, and at no other time.

| Source | What is taken from it |
|---|---|
| **Kuro Games' wiki** — 库街区 鸣潮WIKI, <https://wiki.kurobbs.com> (through its API at `api.kurobbs.com`) | The catalogue: names, rarities and icons of items, dishes, weapons and resonators; recipes; what each build costs; resonator art and head icons (the wiki's 头像 list); the six element icons the wiki's own pages use; the 贝币 icon; boss portraits; the pictures of the shops it has a page for. |
| **wuwatracker.com** — an unofficial fan-made site | **Nothing is downloaded from it.** The app can read the pull-history file that a user exports from that site themselves; the shape of that file is wuwatracker's. Which weapon a pull is, the app knows from `assets/pull_names.json`: pairings made by hand by people naming their own pulls (not taken from any site), and, for the weapons nobody has named yet, the game's own English name beside its Chinese one, checked in the game by hand. |
| **Arikatsu/WutheringWaves_Data** — <https://github.com/Arikatsu/WutheringWaves_Data>, which describes itself as "A repository containing datamined data for the game Wuthering Waves" | The experience tables for resonator, weapon and echo levels. The shops' tables -- what each sells, its limits and prices, and where its map mark is -- (`tools/fetch_shops.py`). The English names: the game's English text table paired with its Chinese one (`tools/fetch_english.py`), which every search box finds things by. And the check on what each build costs: where Kuro's wiki has a row wrong, `assets/build_fixes.json` has the row as the game charges it, confirmed there (ten builds; a row the wiki has right is not in it). The repository states no licence; the data in it is the game's. |

The English names of the game's places and factions on the 猜谜 page are the game's own words,
checked in the game by hand.

The images and data obtained this way remain the property of Kuro Games. Thanks to the people who
maintain these sources, and to wuwatracker for a pull history that can be exported at all.

## 4. Interface icons

The thirteen page icons in the navigation and the phone's drawer, each with a solid twin for the
page you are on (`web/src/components/pages.svg`), the help site's icons (`site/src/components/icons.svg`:
those page icons, a PC, a home server, a laptop, a phone, a crossed-out ID card and the download
button's tray, arrow and check) and the five weapon-type icons (长刃, 迅刀, 佩枪, 臂铠, 音感仪;
`src/wuwa_vision/web/static/icons/`) were made for this project and are under its Apache licence:
drawn with Google Gemini to the project's prompts, then traced here. So is the four-pointed star beside 星声 on
总览.

The six markers of a kind of shop (a basket, a bowl, a medicine bottle, a hammer on an anvil,
two arrows round a coin, a shop front, each white on a black octagon;
`src/wuwa_vision/web/static/icons/shop-*.webp`) were generated for this project with Google
Gemini, from a prompt written for it, then cut out and resized here. They are under the
project's Apache licence like the other drawings. They are drawn after the way a map marks a
shop, and copy no marker of the game's.

The five pictures of 更新's parts (图鉴: a book under a download arrow; 手动修改: a pencil on a
card; 英文名: an A and a 文 with a wrench between them; 识别: an eye in a scan's corners with a
warning sign; 数据: a database with a bin;
`src/wuwa_vision/web/static/icons/upd-*.png`) were generated
for this project with Google Gemini in the same way, cut out and made into masks here, and are
under the project's Apache licence. So are the language button's two cards, one with A and one
with 文 (`lang-a.png`, `lang-zh.png`, and the card's outline `lang-card.png`), which the page
stacks and slides past each other. 我的角色 uses 共鸣者's page icon. A user who would rather see other pictures for
the weapon types can put their own in the folder kept for that
(`src/wuwa_vision/web/static/icons/game/`); the project puts none there.

The other line icons in the interface (the effect icons on dishes, the search, filter and menu
icons) are taken or adapted from two open-source sets, with a few simple ones drawn in the same
style:

- **Feather** — <https://feathericons.com> — MIT License, Copyright (c) 2013-2023 Cole Bemis.
- **Lucide** — <https://lucide.dev> — ISC License, Copyright (c) Lucide Icons and Contributors.
  Lucide began as a fork of Feather, and its licence keeps Feather's MIT notice for the icons
  derived from it.

Both notices are reproduced in full in section 6. The app's own icon (favicon) was drawn for this
project and is under the project's Apache licence. No interface icon is taken from the game.

The interface uses whatever fonts the device already has; none is bundled.

## 5. Software this is built with

Declared licences, as read from each package's own metadata at the versions installed when this
file was written.

**The app (Python)**

| Package | Licence |
|---|---|
| NumPy | BSD-3-Clause (with 0BSD, MIT, Zlib and CC0-1.0 parts) |
| Pillow | MIT-CMU |
| OpenCV (`opencv-python-headless`) | Apache-2.0 |
| FastAPI | MIT |
| Uvicorn | BSD-3-Clause |
| RapidOCR (`rapidocr-onnxruntime`) | Apache-2.0 |
| ONNX Runtime | MIT |
| Pydantic, pydantic-settings | MIT |
| pypinyin | MIT |
| PyTorch, torchvision (optional: recognition) | BSD-3-Clause |
| Transformers (optional: recognition) | Apache-2.0 |
| scikit-image (optional: recognition) | BSD |
| windows-capture (optional: live capture on Windows) | MIT |
| pywin32 (optional: live capture on Windows) | PSF |

**Tailscale (in the home's images)**

The server's image (D183, D238) carries Tailscale's own programs, taken unchanged from its
container image, `tailscale/tailscale`, with only the server's Serve settings and defaults put
in. For compose files from before D238, that image is also published again as
`ghcr.io/oguessyky/wuwa-inventory-vision-tailscale` (D191), unchanged in the same way. Tailscale
is © Tailscale Inc. & contributors, under the BSD-3-Clause licence; its text is in
`deploy/tailscale-image/TAILSCALE-LICENSE` and inside both images at
`/usr/share/licenses/tailscale/LICENSE`.

**Kubernetes' pause image (in the older compose file)**

The server's compose file before D238 runs `registry.k8s.io/pause:3.10`, unchanged, to hold the
network the app and its Tailscale share. It is pulled by Docker from the Kubernetes project's own
registry; nothing of it is in this repository, and the current compose file does not use it.
It is part of Kubernetes, © The Kubernetes Authors, under the Apache License 2.0.

**Python itself (in the release packages for Windows)**

The *full* and *scanner* release packages carry **Python 3.12.10** in `python/`: python.org's own
portable build (the `python` package on nuget.org), unchanged, signed by the Python Software
Foundation. © Python Software Foundation; under the PSF License Agreement, whose text ships
beside it as `python/LICENSE.txt` (with the notices of what it includes). The repository does
not carry it.

**The pages (built ahead of time; no Node at run time)**

| Package | Licence |
|---|---|
| Next.js | MIT |
| React, React DOM | MIT |
| Tailwind CSS | MIT |
| TypeScript (build only) | Apache-2.0 |
| Playwright (tests only) | Apache-2.0 |

**Models**

- **DINOv2** (`facebook/dinov2-base`, Meta AI) — Apache-2.0. Downloaded at setup into `data/`; not
  part of this repository.
- The text-recognition models that RapidOCR runs are **PP-OCR** models from PaddleOCR — Apache-2.0.

## 6. Notices reproduced

### Feather

```
The MIT License (MIT)

Copyright (c) 2013-2023 Cole Bemis

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### Lucide

```
ISC License

Copyright (c) 2026 Lucide Icons and Contributors

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
```
