# How to scan

You scroll the bag in the game; it reads each tile off the screen. It presses no keys and never moves your character: it only looks.

## Start

1. Double-click **`扫描 Scan`** and, within 60 seconds, press **Alt + Tab** to the game (on a Mac, click the game window).
2. Open the bag. A scan page opens in the browser; its top bar says when to move: **Ready (green)** scroll or click, **Reading… (yellow)** wait.

## Scroll

- Scroll slowly, a page at a time, keeping at least one row from the last screen.
- Scroll each tab: **Weapons, Supplies, Resources, Materials**. When the count read matches the game's own at the top, the tab is complete.

## Click

Click an item and it reads the name and the **Owned** count from the detail panel, the surest count there is. It takes about 3 seconds; wait for **Ready** before the next. What you click is remembered.

Tiles marked **to confirm** (items drawn identically, or new in a patch) want one click; for new items, update the catalogue first ([Updating](/update)).

## Finish

Press **F9**, or **Stop the scan** twice on the scan page or your phone. Everything read is kept. If F9 is taken, see [Troubleshooting](/troubleshooting).

With a server, each tab is sent as it is done; if the server cannot be reached it scans anyway and sends it next time.

## Watch the scan on your phone

With one screen, the game hides the scan page. Follow it on your phone instead.

Install [Tailscale](https://tailscale.com) on the PC and the phone, signed in to the same account.

Double-click `扫描 Scan` as usual. It prints `phone page:` and an address like `http://your-pc.your-tailnet.ts.net:8713`, also at the top of the scan page. Open it on the phone and bookmark it: it never changes.

Upright, the phone shows the progress and what the scan needs; sideways it adds the boxes.

Only your own Tailscale devices can open it. The phone can only look or stop the scan, never shows a picture of the game, and opens only while the scan runs. Set a long screen timeout. Trouble? See [Troubleshooting](/troubleshooting).

To keep a scan to this computer, run this in the program's folder:

```
uv run python -m wuwa_vision live --identify
```
