# Install on Windows

This page is about the **full** package: the scanner and the pages on the same Windows PC. To look from your phone anytime, see [A home on a NAS](/home).

## 1. Download

On the [GitHub releases page](https://github.com/oguessyky/wuwa-inventory-vision/releases/latest), download `wuwa-inventory-vision-<version>-full.zip`.

**Before you unzip it:** right-click the downloaded zip → **Properties** → tick **Unblock** at the bottom → OK. Otherwise Windows asks about every file in it ("Open File - Security Warning ... Unknown Publisher"). If it asks anyway, it is safe to press **Run**: the files are the package's own.

Unzip it somewhere short, such as `C:\wuwa-vision`, and leave the folder there (the setup builds on the Python inside it; moving it means setting up again).

## 2. Set it up (once)

Double-click **`1 安装 Setup`** in the folder. It says what it finds and asks before each step:

- the software it needs (with the PyTorch that fits your graphics card);
- the recognition model (about 346 MB);
- the item catalogue from Kuro's official wiki (a few minutes).

Python is included in the package: nothing to install first. To take every default without being asked, run this in PowerShell:

```
powershell -ExecutionPolicy Bypass -File setup.ps1 -Yes
```

## 3. Scan the bag

Double-click **`2 扫描 Scan`**. Then:

1. Press **Alt + Tab** to switch to the game, and open the bag.
2. Scroll down slowly, a page at a time, through each tab (Weapons, Supplies, Development Materials, Resources).
3. To read a thing's count exactly, click it in the game.
4. Press **F9** when you are done. Everything read so far is kept.

A scan page opens in your browser while it runs, showing what it is reading and which tabs are not scanned yet. More tips: [How to scan](/scan).

## 4. See the results

Double-click **`3 总览 Dashboard`**, then open <http://127.0.0.1:4000> in your browser. The pages work while that window is open.

The first time, a short guide walks you through the Overview. What each page is for: [The pages](/pages).

![Overview](screens/en/dashboard.png)

## On your phone?

Install [Tailscale](https://tailscale.com) on the PC and the phone, signed in to the same account: the Dashboard window then prints an address the phone can open. To look anytime (with the PC off, too), use a [home](/home) instead.

## Stuck?

See [Troubleshooting](/troubleshooting).
