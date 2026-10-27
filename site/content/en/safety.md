# Safety and privacy

## What it does to the game

**It only looks at the screen.** It reads the pixels the screen shows, the same as your eyes do.

- No memory reads, no injection, no changes to the game's files, no network capture.
- It never moves your character, fights or farms.
- It never uses, crafts, sells or discards anything: nothing that changes your account.
- On Windows it works only inside menus such as the bag; on a Mac it never presses anything at all.
- It reads only while the game itself is in front; switch away and it pauses.

This is an unofficial, fan-made tool. It is built to avoid anything that could carry a risk, but it is not affiliated with or endorsed by Kuro Games: whether to use it is your decision.

## Your data

- **Your player ID is removed.** The game shows your player ID (UID) all the time; it is taken out of every picture before it is saved or shown.
- **Everything stays on your own devices**: your PC, or your own home. Nothing reaches the author: no statistics, no crash reports, no advertising.
- The pages open on this PC only; to look from your phone you use **your own** Tailscale network, never the open internet.
- A scanner sends its home only what it read and the small item pictures, **never a picture of the whole screen**.

## When it uses the internet

Only these times, and each one started by you:

- **Updating the catalogue:** item, dish and shop data and pictures from Kuro's official wiki; the game's data tables from GitHub.
- **Setting up:** the software it needs (Python packages, PyTorch, the recognition model).
- **Sharing with your own devices:** through Tailscale, to devices on your own network.
- **A home:** syncing between a scanner and your own home, inside your own Tailscale network.
- **Updating a scanner:** when you double-click "4 更新 Update" and the home is newer, that version from this project's GitHub releases.

The full privacy policy: [PRIVACY.md](https://github.com/oguessyky/wuwa-inventory-vision/blob/main/PRIVACY.md).

## Licence and credits

The code is under the Apache License 2.0: see [LICENSE](https://github.com/oguessyky/wuwa-inventory-vision/blob/main/LICENSE) and [TERMS.md](https://github.com/oguessyky/wuwa-inventory-vision/blob/main/TERMS.md). Every name, icon, portrait and artwork from Wuthering Waves belongs to Kuro Games; the program ships none of the game's images, and downloads them to your own computer. The sources, and the software it is built with: [CREDITS.md](https://github.com/oguessyky/wuwa-inventory-vision/blob/main/CREDITS.md).
