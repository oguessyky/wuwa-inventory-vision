# Install on a Mac

A Mac uses Kuro's own Mac client. The program is the same as on Windows; only the files you double-click are `.command` files, and the Windows Python is not included. On a Mac it **only reads**: it never presses anything for you. Each Mac package's own guide is in [Package guides](/guides#mac-full).

## 1. Install Python first

Open Terminal and run:

```
brew install python@3.12
```

(No Homebrew yet? Install it first with the one line on <https://brew.sh>.)

## 2. Download and unzip

From the [GitHub releases page](https://github.com/oguessyky/wuwa-inventory-vision/releases/latest), download:

- Everything on one Mac: `wuwa-inventory-vision-<version>-mac-full.zip`
- The Mac only scans, sending to a [home](/home): `wuwa-inventory-vision-<version>-mac-scanner.zip`

Unzip it somewhere it can stay.

## 3. Set it up (once)

Double-click **`1 安装 Setup`**. The first time, macOS may say it cannot verify the developer: right-click the file → **Open** → **Open** again.

## 4. Allow Screen Recording

macOS lets no program read another window until you say so:

1. **System Settings → Privacy & Security → Screen & System Audio Recording**
2. Switch on the app you run it from (usually Terminal): not Python, not the game. After the first refused run it is in the list for you.
3. Quit Terminal, open it again, and try again.

## 5. Scan

With the scanner package, first double-click **`2 连接主机 Connect home`** (see [A home on a NAS](/home)).

Then double-click **`扫描 Scan`**:

1. **Click into the game window**: on a Mac only the window you click into is in front; pointing the mouse at it is not enough.
2. Open the bag and scroll each tab slowly; click a thing to read its count exactly.
3. When you are done, go back to the scan's Terminal window and press **Ctrl+C**. There is no F9 on a Mac: a key that works over every app needs the Accessibility permission, which this project never asks for.

## 6. See the results

mac-full: double-click **`3 总览 Dashboard`** and open <http://127.0.0.1:4000> in your browser. With a home, open the home's address instead.

## Stuck?

Nothing captured on a Mac is almost always Screen Recording not being allowed. See [Troubleshooting](/troubleshooting).
