# Troubleshooting

## Setting up

### "Security Warning ... Unknown Publisher" when opening a file

A zip downloaded by a browser marks every file in it as from the internet. **Before** unzipping: right-click the zip → **Properties** → tick **Unblock** → OK, then unzip. Already unzipped? When it asks, it is safe to press **Run**: the files are the package's own.

### "wuwa" or python will not start: blocked by a policy

Some PCs' security policy blocks it. Run it as a module instead of `wuwa`:

```
uv run python -m wuwa_vision live --identify
```

If python itself is blocked: install Python 3.12 from python.org, then double-click **`1 安装 Setup`** to set up again.

### The page is blank, or says it is not built

The setup did not finish: double-click **`1 安装 Setup`** and run it again.

## Scanning

### The scan stops at once, or says the window is wrong

The game itself has to be in front: a browser tab of the same name does not count. After it starts you have 60 seconds: press **Alt + Tab** to switch to the game. Away too long (2 minutes) and it stops; what it read is kept. To check it can find the game first:

```
uv run python -m wuwa_vision windows
```

Start scanning once you see `guard: window OK`.

### It says F9 is taken and will not start

Another program has F9; the terminal lists the keys that are free. Start with another one, for example:

```
uv run python -m wuwa_vision live --identify --panic-key F10
```

### A tile is red, or its name is a question mark

Some items have identical icons: only clicking tells them apart. Click the item in the game and wait for the top of the scan page to say **Ready**. Once clicked it is remembered.

### Items from a new version have no names

The catalogue is out of date: on **Update → Catalogue**, press "Update from the wiki", then click those items in the game.

### A count is wrong

Click the item in the Inventory, click the number, change it, and press Enter. Your number stays until the next scan reads the item.

### Clicking an item takes seconds

That is normal: reading the details panel on the right takes about 2.5–3 seconds. Click the next one once you see **Ready**.

### Nothing is captured on a Mac

Almost always Screen Recording is not allowed: **System Settings → Privacy & Security → Screen & System Audio Recording**, switch on your terminal, then quit the terminal and open it again. To check:

```
uv run python -m wuwa_vision platform
```

## The server and the phone

### The phone cannot open the site

The PC (or the server) and the phone both need Tailscale, signed in to the same account. With one PC only, start the pages without `--local`, then open the address it prints on the phone.

### The server's address does not open

Check the Tailscale container's log for a login: a `TS_AUTHKEY` left as `tskey-auth-PUT-YOURS-HERE`, or a key already used up, will not do. In the Tailscale admin console, `wuwa-server` must show as connected.

### The server asks to log in again after months

Key expiry is on for that device: turn it off for `wuwa-server` in the Tailscale admin console, and redeploy.

### Connecting to the server says the key is wrong

The key is `data/server.key` in the server's storage path. Download it with the NAS's file manager (it lands in Downloads), double-click **`2 连接服务器 Connect server`** and press Enter at the key: it takes the newest `server*.key` in Downloads, so downloading it more than once is fine.

### The server will not start after an update: "joining network namespace of container: No such container"

The server's app lives in the Tailscale container's network. The update made a new Tailscale container, and the old app container still points at the one that was removed. In the NAS's Docker app, **stop** the project and **deploy** it again (rebuild, not just start); or delete only the `…-wuwa-1` container and start the project. The data is in the project's `data` folder and is not touched.

From v1.1.3 the compose file has a tiny third container, `net`, that holds the network and that no update replaces, so this does not happen again. A server set up before v1.1.3: paste the new compose file into the project once, then deploy.

### It says "cannot join network namespace of a non running container"

The project's containers were started out of order: press start once more.

### A scan says the versions differ

What the two send each other changed: update the scanner and the server to the same version, see [Updating](/update).

### The first catalogue download takes long

The first time it downloads over a thousand entries, and the time goes on waiting for the wiki's server to answer, not on your connection's speed. The page shows how far it is and how long is left, and what fails is retried by itself. After that, only what is new is downloaded.

## Still stuck?

Open an issue on [GitHub](https://github.com/oguessyky/wuwa-inventory-vision/issues) saying what you did and what you saw (cover your player ID in any screenshot).
