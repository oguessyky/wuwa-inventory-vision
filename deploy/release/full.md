# WuWa Inventory Vision {version}: the full program

**With a picture for every step:** open `START-HERE.html` in this folder (图文指南，用浏览器打开).

Reads your Wuthering Waves bag **off the screen** and turns it into a list of what you own, then
works out what you still have to farm. This package has everything: the **scanner** (reads the
bag while you scroll it) and the **dashboard** (the pages: 总览, 库存, 材料, 共鸣者, 武器, 料理,
商店, 规划…), on one PC. It also holds the files for running the dashboard on a NAS
([docs/nas.md](docs/nas.md)); the separate *server* package is the easier way to do that.

It never touches the game's files, memory or network traffic: only pixels. Nothing you do in it
changes your account, and everything stays on your own computer ([PRIVACY.md](PRIVACY.md)).

## What you need

| | |
|---|---|
| Windows 10 or 11, or macOS | both tested. On macOS: Kuro's own Mac client, and the Screen Recording permission (see the setup) |
| Python | nothing to install: **Python 3.12 is included** (in `python\`, python.org's own build). On macOS: `brew install python@3.12` |
| uv | the setup installs it with winget if it is missing |
| Disk | about 6 GB, most of it PyTorch |
| GPU | optional. An NVIDIA card makes recognition much faster; CPU works |
| Internet | during setup only, to download the packages, the recognition model and the item catalogue |

## 1. Set it up (once)

**Before you unzip it:** right-click the downloaded zip → **Properties** → tick **Unblock** at the
bottom → OK. A zip downloaded by a browser marks every file in it as from the internet, and
Windows then asks about each one ("Open File - Security Warning ... Unknown Publisher"). If it
asks anyway, it is safe to press **Run**: the files are this package's own.

Unzip this folder somewhere short, such as `C:\wuwa-vision`, and leave it there: the setup
builds on the Python inside it, so moving the folder later means running the setup again.

**Double-click `1 安装 Setup`** in the folder. (It runs the line below; you can also open
PowerShell in the folder -- Shift + right-click → *Open PowerShell window here* -- and type it.)

```
powershell -ExecutionPolicy Bypass -File setup.ps1
```

It says what it finds and asks before each step: the packages (with the PyTorch that fits your
GPU), the recognition model (~346 MB), and the item catalogue from Kuro's official wiki (a few
minutes). Add `-Yes` to take every default without being asked. On macOS: `./setup.sh`.

Last, it offers shortcuts: `WuWa Scan` and `WuWa Dashboard` on the Desktop, and a
*WuWa Inventory Vision* folder in the Start menu. Add or remove them later with
`uv run python -m wuwa_vision shortcuts` (`--remove`). After moving the folder, run Setup again.

## 2. Scan

**Double-click `2 扫描 Scan`**, or run:

```
uv run python -m wuwa_vision live --identify
```

Then alt-tab into the game, open the bag (背包), and scroll each tab steadily by hand, about a
page at a time. Click an item and its name and count are read from the game's own detail panel.
Press **F9** when you are done -- everything read so far is kept. A live page,
<http://127.0.0.1:8711/live>, opens in your browser and shows what it is reading.
[docs/scanning.md](docs/scanning.md) has the details.

## 3. Use the dashboard

**Double-click `3 总览 Dashboard`** (the pages run while its window is open), or run:

```
uv run python -m wuwa_vision serve
```

and open <http://127.0.0.1:4000>. With [Tailscale](https://tailscale.com) connected, it prints an
address your own phone can open too; `serve --local` keeps it on this PC.
[docs/dashboard.md](docs/dashboard.md) walks through the pages.

## Later

- **After a game patch**: the 更新 page's *从 Wiki 更新* button fetches the new catalogue.
- **A new version of this program**: unzip it into a new folder, move the `data` folder
  across from the old one -- your scans, names and settings are all in there -- and run the
  setup in the new folder. If this PC scans for a server, **`4 更新 Update`** does it for you
  when the server is newer (it downloads the server's version from GitHub; nothing otherwise).
- **Something wrong**: [docs/setup.md](docs/setup.md) ends with troubleshooting, and the app's
  帮助 page says what to do when something does not work.

Licence: Apache 2.0 ([LICENSE](LICENSE), [NOTICE](NOTICE)); how the project asks to be used:
[TERMS.md](TERMS.md). An unofficial fan-made tool, not affiliated with Kuro Games; the game's
names and pictures are theirs, and are downloaded to your own computer, never shipped in here
([CREDITS.md](CREDITS.md)).
