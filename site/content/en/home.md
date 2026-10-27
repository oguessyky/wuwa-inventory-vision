# A home on a NAS

A "home" is a box that is always on (a NAS, a mini PC, a small server). It keeps the data and shows the pages. The PC with the game does the scanning, and sends each finished tab to the home. Your phone and laptop can then open the results anytime, even with the gaming PC off.

The home is **ready-made**: the program is a published image, and Tailscale comes beside it in the same project. Nothing is built on the NAS and nothing is typed there: you paste one file into the NAS's Docker app.

## What you need

- A NAS (UGOS, Synology, Unraid, QNAP…) or any Linux box with Docker and Compose.
- A free [Tailscale](https://tailscale.com) account. A Tailscale already on the NAS or your PC is fine and is not touched: the home joins your network as a device of its own.

## 1. Get a Tailscale auth key

At <https://login.tailscale.com/admin/settings/keys>, press **Generate auth key** and copy the `tskey-auth-…`. A one-off key is enough: it is used once, on the first start. Keep it to yourself.

## 2. Create the project in the Docker app

In the NAS's Docker app: **Project** → **Create project**:

- **Name:** `wuwa-inventory-vision`
- **Storage path:** an empty folder, such as `/volume1/docker/wuwa-inventory-vision`. The data is kept there; keep it out of anything that syncs from a PC.
- **Compose configuration:** paste the whole of `docker-compose.yaml` from the releases page, and in its `TS_AUTHKEY` line replace `tskey-auth-PUT-YOURS-HERE` with your key.

Then **Deploy**. The Docker app pulls two images, `wuwa-inventory-vision-home` (the program) and `wuwa-inventory-vision-tailscale` (Tailscale's own image under this app's name), and starts them.

## 3. Open it

On a phone or PC signed in to the same Tailscale, open `http://wuwa-home:4000`.

In the Tailscale admin console you will find a new device, `wuwa-home`. Turn its **key expiry** off, or it asks to log in again in six months.

The home opens only from your own Tailscale network; it is never put on the internet.

## 4. Download the catalogue (the first time)

A new home has no catalogue yet: no item names, pictures or recipes. The first time you open it, the guide's last step offers "下载图鉴" (download the catalogue): one click starts it and takes you to the Update page, which shows how far it is and how long is left. The first download takes a while, and what fails is retried by itself.

## 5. Connect a scanner

On the PC with the game, use the **scanner** package:

1. Unblock and unzip it as in [Install on Windows](/install), then double-click **`1 安装 Setup`** (a scanner downloads no catalogue: it takes the home's).
2. Double-click **`2 连接主机 Connect home`**. For the address, Enter alone takes `wuwa-home`; the key is the one line of `data/home.key` in the home's storage path (the NAS's file manager opens it).
3. Double-click **`3 扫描 Scan`** to scan (see [How to scan](/scan)). Each finished tab is sent home.

A second scanner (a laptop, say) uses the same key.

## Backing up

Everything is in the `data` folder inside the storage path: `wuwa.sqlite`, `icons/`, `catalogue/` and `home.key`. Stop the project first for a consistent copy of the database.

## Stuck?

See [Troubleshooting](/troubleshooting).
