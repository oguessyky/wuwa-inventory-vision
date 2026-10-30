# WuWa Inventory Vision {version}: the scanner

**With a picture for every step:** open `START-HERE.html` in this folder (图文指南，用浏览器打开).

The part that runs **on the PC with the game**: it reads your Wuthering Waves bag off the screen
while you scroll it, and sends what it read to your **server** -- the dashboard running on a NAS or
another always-on machine (the *server* package). You look at the result there, from any of your
devices.

It never touches the game's files, memory or network traffic: only pixels. It sends the list of
items and counts and the small tile pictures, **never a screenshot**, and only to the server you
give it, on your own tailnet ([PRIVACY.md](PRIVACY.md)).

> No server yet? Set it up first with the *server* package -- its note says where the address and
> the key this PC needs are. Or use the *full* package, which shows the dashboard on this PC instead.

## What you need

| | |
|---|---|
| Windows 10 or 11, or macOS | both tested. On macOS: Kuro's own Mac client, and the Screen Recording permission (see the setup) |
| Python | nothing to install: **Python 3.12 is included** (in `python\`, python.org's own build). On macOS: `brew install python@3.12` |
| uv | the setup installs it with winget if it is missing |
| Disk | about 6 GB, most of it PyTorch |
| GPU | optional. An NVIDIA card makes recognition much faster; CPU works |
| [Tailscale](https://tailscale.com) | on this PC and on the server, signed in to the same tailnet |

## 1. Set it up (once)

**Before you unzip it:** right-click the downloaded zip → **Properties** → tick **Unblock** at the
bottom → OK. A zip downloaded by a browser marks every file in it as from the internet, and
Windows then asks about each one ("Open File - Security Warning ... Unknown Publisher"). If it
asks anyway, it is safe to press **Run**: the files are this package's own.

Unzip this folder somewhere short, such as `C:\wuwa-scanner`, and leave it there: the setup
builds on the Python inside it, so moving the folder later means running the setup again.

**Double-click `1 安装 Setup`** in the folder. (It runs the line below; you can also open
PowerShell in the folder and type it.)

```
powershell -ExecutionPolicy Bypass -File setup.ps1 -Scanner
```

It installs the packages (with the PyTorch that fits your GPU) and the recognition model
(~346 MB). `-Scanner` skips the item catalogue: the server sends it before every scan. Add `-Yes`
to take every default without being asked. On macOS: `./setup.sh --scanner`.

Last, it offers shortcuts, a question for each place: `WuWa Scan` on the Desktop, and a
*WuWa Inventory Vision* folder in the Start menu (Scan, Update; Connect server only if you say yes
-- it is done once). Add or remove them later with `uv run python -m wuwa_vision shortcuts`
(`--desktop`, `--menu`, `--connect`, `--remove`).

## 2. Give it its server (once)

First download `server.key` from the server's data folder (the NAS's file manager) -- it lands in
Downloads. **Double-click `2 连接服务器 Connect server`**: it asks for the server's address and its key.
For the key, Enter alone takes the newest `server*.key` in Downloads (pasting its one line, or the
file's path, works too). For the address, Enter alone takes `wuwa-server`, the
server's name on Tailscale; the name Tailscale shows (`wuwa-server.your-tailnet.ts.net`) or its
`100.x` address do too -- `http://` and port `4000` are put in. It is the same as running:

```
uv run python -m wuwa_vision server set wuwa-server <the key>
```

It checks the address and the key before saving them. Only a tailnet address is accepted
(`…ts.net` or `100.x`), never a LAN or public one.

## 3. Scan

**Double-click `3 扫描 Scan`**, or run:

```
uv run python -m wuwa_vision live --identify
```

It first fetches what the server knows (the catalogue, names given on a phone), then waits for you
to alt-tab into the game. Open the bag (背包) and scroll each tab steadily by hand, about a page
at a time; click an item to have its name and count read from the game's own panel. Press
**F9** when you are done. Each tab is sent to the server as soon as it is finished, the rest when the scan
ends -- then open the server's address on your phone. [docs/scanning.md](docs/scanning.md) has the
details.

If the server cannot be reached, the scan still runs and is kept on this PC; it is sent with the
next scan, or now with:

```
uv run python -m wuwa_vision push
```

| | |
|---|---|
| `uv run python -m wuwa_vision server` | where this PC's scans go, and how many are waiting |
| `uv run python -m wuwa_vision pull` | fetch what the server knows, now |
| `uv run python -m wuwa_vision server forget` | stop sending; keep the scans on this PC |

## Uninstalling

**double-click `5 卸载 Uninstall`**. It removes the shortcuts, the installed
environment, the recognition model and the program's files, and asks first whether your scans
and settings (the `data` folder) go too -- they stay unless you say yes.

## If something is wrong

| | |
|---|---|
| `server set` says 连不上服务器 | the address does not answer from this PC: open it in a browser here, and check both are on the tailnet |
| … says 钥匙 | the key is not the server's: it is the one line in `server.key` in the server's data folder |
| … or a push says the versions differ | the two cannot talk: update both to the same version |
| `python` or `wuwa` will not start | see the troubleshooting at the end of [docs/setup.md](docs/setup.md) |

Updating: before each scan the scanner says whether it or the server is missing changes of its
own; a release that changed only the server needs no new scanner (the server's **更新 › 数据 › 版本**
lists them). When the scanner is the one behind, **double-click `4 更新 Update`**: it downloads
the server's version from this project's GitHub releases, checks it against the release's
checksums, puts it over this folder (your `data` stays) and runs the setup again. It fetches
nothing unless the server is newer.

Licence: Apache 2.0 ([LICENSE](LICENSE), [NOTICE](NOTICE)); how the project asks to be used:
[TERMS.md](TERMS.md). An unofficial fan-made tool, not affiliated with Kuro Games
([CREDITS.md](CREDITS.md)).
