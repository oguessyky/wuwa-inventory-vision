# WuWa Inventory Vision {version}: for macOS

The same program as the Windows *full* package, with double-click files for a Mac (`.command`)
instead of Windows' (`.cmd`), and without the Windows Python. It reads your Wuthering Waves bag
off the screen while you scroll it in **Kuro's own Mac client**; it never touches the game's files,
memory or network traffic, only pixels ([PRIVACY.md](PRIVACY.md)).

## What you need

| | |
|---|---|
| macOS | with Kuro's own Mac client of Wuthering Waves |
| Python 3.12 | `brew install python@3.12` |
| uv | the setup installs it if it is missing |
| Screen Recording | System Settings › Privacy & Security › Screen Recording: allow your terminal |
| Disk | about 6 GB, most of it PyTorch |

## 1. Set it up (once)

Unzip this folder somewhere it can stay, then **double-click `1 安装 Setup`**. The first time,
macOS may say it cannot check the file: right-click it, choose **Open**, then **Open** again. It
runs `./setup.sh`.

Last, it offers shortcuts, a question for each place: on the Desktop, and in Applications, where
Launchpad and Spotlight find them -- each opens the package's own file in Terminal, with the app's
icon. `uv run python -m wuwa_vision shortcuts --remove` takes them away.

## 2. Scan

**Double-click `2 扫描 Scan`**, then **click into the game** (on a Mac the game counts as in front only once you click it),
open the bag and scroll each tab by hand.
Click an item to have its name and count read from its panel. When you are done, press
**Ctrl+C** in the scan's own window (on a Mac there is no F9: a key that works over every app
would need the Accessibility permission, which this project never asks for).
macOS is passive-only: nothing is ever clicked or typed for you. [docs/setup.md](docs/setup.md)
has what differs on a Mac (Screen Recording, the focus click).

**One screen?** Follow the scan on your phone. With [Tailscale](https://tailscale.com) signed in on
this computer and the phone, run this in the program's folder instead of the double-click, then
open the `phone page:` address it prints (port 8713) on the phone:

```
uv run python -m wuwa_vision live --identify --share
```

## 3. The dashboard

**Double-click `3 总览 Dashboard`** and open <http://127.0.0.1:4000> while its window is open.
[docs/dashboard.md](docs/dashboard.md) walks through the pages.

## Later

- **Updating**: when this Mac scans for a server and the server is newer, **double-click
  `4 更新 Update`**: it downloads the server's version from this project's GitHub releases, checks
  it, puts it over this folder (your `data` stays) and runs the setup again.
- **Uninstalling**: **double-click `5 卸载 Uninstall`**. It removes the shortcuts, the installed
  environment, the recognition model and the program's files, and asks first whether your scans
  and settings (the `data` folder) go too -- they stay unless you say yes.
- **Something wrong**: [docs/setup.md](docs/setup.md) ends with troubleshooting.

Licence: Apache 2.0 ([LICENSE](LICENSE), [NOTICE](NOTICE)); how the project asks to be used:
[TERMS.md](TERMS.md). An unofficial fan-made tool, not affiliated with Kuro Games
([CREDITS.md](CREDITS.md)).
