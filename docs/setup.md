# Setting up

How to install WuWa Inventory Vision and check that it works. For what the project is, see the
[README](../README.md); for using it, [scanning](scanning.md) and [the dashboard](dashboard.md).

**You do not need a dataset.** A ready-made recognition gallery ships with it
(`assets/gallery_pack.npz`). Nothing has to be captured by hand to get started.

## 1. Prerequisites

| | |
|---|---|
| Python | **3.12** exactly — install from python.org, *not* the Microsoft Store (PyInstaller cannot bundle the Store build). The environment is built on this one; without it the setup stops and says so. The *full* and *scanner* release zips carry it already, in `python\` (D175), and `setup.ps1` takes that one first |
| uv | `winget install astral-sh.uv` or `pip install uv` |
| GPU | optional — an NVIDIA card makes recognition ~30× faster, CPU works otherwise |

The easiest way in is a release: <https://github.com/oguessyky/wuwa-inventory-vision/releases>. Take the **full** zip (or **scanner**,
for a PC that sends to a home), unzip it, and follow its `START-HERE.md` -- on Windows it
carries Python itself. Or take the source:

```bash
git clone https://github.com/oguessyky/wuwa-inventory-vision.git
cd wuwa-inventory-vision
```

## 2. One command (D70, D85)

```bash
powershell -ExecutionPolicy Bypass -File setup.ps1
```

```bash
./setup.sh
```

That is the whole install — the first line on Windows, the second on macOS. In order it:

1. works out what the machine is and says so;
2. installs the dependencies with the PyTorch that belongs on it — CUDA 12.8 for an NVIDIA card
   (checking the driver is new enough; the CUDA *Toolkit* is never needed, the wheels carry the
   runtime), the XPU wheels for an Intel Arc or Core Ultra iGPU, MPS on Apple Silicon, CPU otherwise;
3. fetches the DINOv2 weights (~346 MB) into `data/models/dinov2-base/`;
4. **downloads the catalogue** from Kuro's official wiki if it is not there yet — items and icons,
   recipes, resonator and weapon builds, portraits, level tables, boss art (~40 MB, a few minutes).
   Every page except the raw scan reads from it. It asks first, and skipping it is fine: the 更新
   page can do it later;
5. prints what torch can actually see.

| flag | |
|---|---|
| `--yes` | take every default, ask nothing |
| `--check` | only look and report; install nothing |
| `--zip URL_OR_PATH` | install the catalogue from a published archive instead of crawling the wiki (much faster). A Google Drive share link works as is, as does a direct URL or a local path |

## 3. macOS: grant Screen Recording first (D71)

macOS will not let anything read another window's pixels until you say so, and the failure is
silent — frames come back empty.

1. **System Settings → Privacy & Security → Screen & System Audio Recording**
2. switch on the app you will run `wuwa` *from* — Terminal, iTerm, VS Code — not Python, not the
   game. The first refused run puts that app in the list for you;
3. run it again. If it still refuses, quit and reopen that app.

Without it macOS also blanks every other app's window title, so the game cannot even be found.
The guard checks the permission first and names the app it needs (D109):
`refusing to capture: macOS hides other apps' windows until Screen Recording is allowed: allow
Screen Recording for Visual Studio Code in System Settings…`

Four more things differ on macOS — `uv run python -m wuwa_vision platform` prints them for the
machine it runs on, and whether the game is ready (D152):

- **The game is in front when you click into it** (or Cmd-Tab to it). Pointing the mouse at it is
  not focus on macOS. `live` waits for that click, and pauses when you click away (D151).
- **The panic key is Ctrl+C**, in the terminal that started the scan. There is no global hotkey:
  registering one needs Accessibility permission, and a global key watcher is exactly the keyboard
  hook this project refuses to install. `live` still refuses to start unless it can be stopped.
- **Kuro's Mac client (`WutheringWaves.app`) is identified by its owner**, the app the window
  server says the window belongs to, as on Windows. Under CrossOver / Whisky / Parallels the owner
  is the wrapper, so there **the window is identified by its title** and the owner is printed so
  you can check it.
- **macOS is passive-only.** There is no synthetic-input backend at all, so nothing can be typed
  into any window, right or wrong.

> macOS: tested on hardware against the native client and it works (D109, D151, D196), as Windows
> does.

## 4. Check it works — no game needed

```bash
uv run python -m wuwa_vision platform
```

```bash
uv run python -m wuwa_vision serve
```

The first says which system it found and how `live` scans on it. The second serves the main app:
open <http://127.0.0.1:4000>. Before a first scan there is nothing owned to show; after one,
the 库存 page lists what you have.

![The 库存 page after a full scan of a real inventory](screens/inventory.png)

> `uv sync` also installs a shorter `uv run wuwa …` alias. It is the same program, but Windows
> Application Control blocks it on some machines, so these docs spell out the module form —
> which works wherever Python 3.12 from python.org is what the environment was built on. See
> [Troubleshooting](#wuwa-will-not-start-at-all) below.

<details>
<summary>The same thing by hand</summary>

```bash
uv sync --extra recognition --extra capture   # --extra recognition pulls PyTorch, ~2.5 GB, once
uv run python tools/fetch_model.py            # DINOv2 weights
uv run python tools/fetch_catalogue.py        # items + icons  (--from-zip "<link>" is much faster)
uv run python tools/fetch_recipes.py          # dishes, potions, 食谱
uv run python tools/fetch_builds.py           # resonator + weapon build costs, card and 立绘 art
uv run python tools/fetch_icons.py            # head icons, element icons, the 贝币 icon
uv run python tools/fetch_levels.py           # level / EXP tables
uv run python tools/fetch_shops.py            # what every shop sells: limits and prices
uv run python tools/fetch_bosses.py           # boss portraits
uv run python -m wuwa_vision seed             # embed the catalogue icons into the gallery
```

Each fetch only downloads what the wiki added since the last run, so re-running one after a patch
is cheap. `fetch_catalogue --make-zip` packs `data/catalogue/` for publishing, and
`uv run python -m wuwa_vision pack` writes the gallery's reference entries back to
`assets/gallery_pack.npz`.

Item recognition needs none of this: the shipped pack already holds the official catalogue embedded
(names, rarities, embeddings; no images), and is imported the first time the scanner runs. On 126
real crops it names 111 right and 0 wrong; the other 15 are left for a click (10 items drawn
identically to another, 5 not in the catalogue). The catalogue download is what gives you the
*pictures*, and everything the other pages are built from.

The icons are Kuro Games' assets: local recognition use only, gitignored, never redistributed.
</details>

---

## Where everything lives

All state lives in `data/` (gitignored): `wuwa.sqlite`, `icons/`, `models/`, `catalogue/`, `runs/`,
`backups/`. Delete `data/wuwa.sqlite` and `data/icons/` to start clean — or use 清空扫描数据 on the
更新 page, which backs both up first. The shipped pack is imported again on the next scan.

Tools, run with `uv run python tools/<name>.py`: `setup` (everything above), `fetch_model`,
`fetch_catalogue` (`--from-zip`, `--make-zip`), `fetch_recipes`, `fetch_builds`, `fetch_icons`,
`fetch_levels`, `fetch_shops`, `fetch_bosses`, `make_pull_names` (ship the pulls you named by hand),
`make_nas_bundle` (lay the app out for a NAS, [nas.md](nas.md)).

---

## Troubleshooting

### `wuwa` will not start at all

```
error: Failed to spawn: `wuwa`
  cause: An Application Control policy has blocked this file. (os error 4551)
```

Windows Smart App Control / WDAC blocks the unsigned `wuwa.exe` console shim that `uv sync`
generates in `.venv\Scripts\`. Nothing is wrong with the install — the policy refuses to launch an
unsigned executable, and that shim is one.

This is why every command in these docs is written as `uv run python -m wuwa_vision …`
rather than `uv run wuwa …`. The module form runs the same code through the signed
interpreter, so it is unaffected by the policy. If `uv run wuwa` works on your machine, the
two are interchangeable.

### `python` will not start either

```
error: Failed to spawn: `python`
  cause: An Application Control policy has blocked this file. (os error 4551)
```

The same policy, one step further down: the interpreter itself is unsigned. That happens when
the machine had no Python 3.12 from python.org when the environment was made, and `uv` fetched
a build of its own instead. `type .venv\pyvenv.cfg` shows it: the `home =` line points into a
`uv\python\cpython-3.12…` folder rather than at `…\Programs\Python\Python312`.

Install Python **3.12** from python.org, then make the environment again:

```bash
Remove-Item -Recurse -Force .venv
```

```bash
powershell -ExecutionPolicy Bypass -File setup.ps1
```

The project now tells `uv` to use only a Python you installed (`python-preference` in
`pyproject.toml`), so a machine without one is told so at setup instead of being given a
build that will not start.

### Nothing is captured, or every frame is empty

On macOS that is the Screen Recording permission — see [step 3](#3-macos-grant-screen-recording-first-d71).
`uv run python -m wuwa_vision platform` checks it, and finds the game, on either OS.
On Windows, run `uv run python -m wuwa_vision windows` and check what the guard says: capture needs
the **game process** to own the foreground window, and it re-checks that on every frame.
