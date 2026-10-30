# Privacy Policy

Effective 30 October 2026.

This Privacy Policy is provided in English and may be translated into other languages for your
convenience. In the event of any conflict or discrepancy between the English version and a
translated version, the English version shall prevail and be the legally binding document. The
translated versions are for reference only and do not carry any legal weight.

## 1. Who this covers

WuWa Inventory Vision ("the app") is an unofficial, fan-made tool by oguessyky. It is software you
run on your own computer. It is not an online service: the author runs no server that receives
your data, and has no account system, no analytics and no way to see what you do with the app.

This policy says what the app keeps on your own machines, and the few times it talks to anything
else -- each of them something you start.

## 2. What the app keeps, and where

Everything below is kept in the app's data folder on the computer that runs it (and, if you set one
up, on your own server -- section 3). None of it is sent to the author.

- **Pictures of the game's bag while you scan.** The app captures only the game's own window. The
  player UID shown in the game (特征码) is blacked out before any picture is saved or shown. Names of
  co-op players can appear in a capture.
- **What is read from those pictures**: item names, counts, levels, refinement, who carries which
  weapon, and the 贝币 and 星声 you have; the small picture of each item tile; when each scan was
  made.
- **What you enter**: targets, base amounts, plans, corrections to names and counts, and English
  names you type.
- **Your pull history, if you import it.** You choose a file exported from wuwatracker. The app
  keeps only how many copies of each resonator and weapon it lists. The player ID and the list of
  pulls are not kept.
- **Settings in your browser.** The pages remember small things in your browser's local storage:
  filters and sort orders, whether the navigation is folded, whether you have finished the
  first-time guide. These stay in that browser. The app sets no cookies and does no tracking.
- **Shortcuts, if you ask for them.** When setup asks and you say yes, or you run `wuwa shortcuts`,
  the app puts shortcuts in the places you said yes to: your Desktop, and your Start menu (on a
  Mac, Applications). They hold only where the app's own files are. `wuwa shortcuts --remove` takes
  them away again, and so does uninstalling.
- **Uninstalling.** `5 卸载 Uninstall` removes the shortcuts and the app's folder. It asks first
  whether your scans and settings go too, and keeps them unless you say yes. Nothing is sent
  anywhere.

## 3. What leaves your computer, and only when you start it

- **Updating the catalogue** (更新 page, or the fetch tools). The app downloads item, dish, recipe and
  shop data and pictures from Kuro Games' wiki (`wiki.kurobbs.com`, `api.kurobbs.com`) and game data
  tables from GitHub (`github.com`, `api.github.com`, `raw.githubusercontent.com`). It sends nothing
  of yours: these are downloads. Like any website, those services see your IP address, under their
  own privacy policies.
- **Setting up.** The installer downloads the software the app needs (Python packages, PyTorch, the
  recognition model and the catalogue pack) from their hosts, including a file hosted on Google
  Drive. This happens when you install, not while you use the app.
- **Sharing with your own devices.** `serve` (unless `--local`) and `wuwa live --share` make the
  pages reachable from devices on your own Tailscale network, through Tailscale. The app's server
  itself listens only on this computer. Tailscale's own privacy policy covers its service.
- **Your own server.** If you connect a scanner to a server (`wuwa server set`), the scanner fetches
  the catalogue from it and sends each finished scan to it: the rows that were read and the item
  pictures, never a full picture of the screen. The server must be on your own Tailscale network or
  on the same computer. To connect, the scanner needs the server's key: when you press Enter at the
  key, it reads the newest `server.key` you downloaded into your Downloads folder, on that computer,
  and keeps the key in its own data folder. It looks at nothing else in Downloads.
- **Updating a scanner.** When a scanner's server is newer and you run `4 更新 Update` (`wuwa update`),
  it downloads that version's package and checksums from this project's releases on GitHub
  (`github.com`, and the file host GitHub sends it to). It sends nothing of yours. Without a
  server, or with one that is not newer, it downloads nothing.
- **Export.** Anything you export is written to a file you choose.

Nothing else leaves your computer: no telemetry, no crash reports, no advertising, no downloads in
the background.

## 4. Who else receives your data

No one, unless you send it. The author does not receive, sell or share any data, because the app
sends none to the author.

## 5. Your control

- To see what is kept, open the data folder.
- To delete it, delete the data folder (backups are in `data/backups`). On a server, delete its
  data folder there. Take the shortcuts away with `wuwa shortcuts --remove`.
- To clear what a browser remembers, clear that site's data in the browser.

## 6. Children

The app is not directed at children under 13. It collects nothing from anyone for the author.

## 7. Changes

This policy is kept with the app, as `PRIVACY.md`. When it changes, the date at the top changes,
and the change is recorded in the project's history.

## 8. Contact

Questions about this policy: open an issue in the project's repository, or contact the author,
oguessyky.
