# WuWa Inventory Vision {version}: the server

**With a picture for every step:** open `START-HERE.html` in this folder (图文指南，用浏览器打开).

The dashboard on a box that is always on -- a NAS, a mini PC, a small server -- for every device
on your own [Tailscale](https://tailscale.com) tailnet: your phone, a laptop, the PC. It holds the
data and shows the pages (总览, 规划, 料理, 材料, 共鸣者, 武器, 商店, 库存…).

It is **ready-made**: the app comes as a published image (for `amd64` and `arm64`), and Tailscale
comes beside it in the same project. Nothing is built on the NAS and nothing is typed there --
no SSH, no script. All it takes is one compose file, pasted into the NAS's Docker app. The server
reads nothing off a screen: scanning is done at the PC with the game, by the *scanner* package,
which sends each finished tab here.

## What you need

- Docker with Compose: the Docker app of a NAS (UGOS, Synology, Unraid, QNAP…) or any Linux box.
- A Tailscale account (free). A Tailscale already on the NAS or your PC is fine and is not
  touched: this server joins your tailnet as a device of its own.

## 1. Get a Tailscale auth key

At <https://login.tailscale.com/admin/settings/keys>, press **Generate auth key** and copy the
`tskey-auth-…`. A one-off key is enough: it is used once, on the first start. Keep it to yourself.

## 2. Create the project in the Docker app

In the NAS's Docker app: **Project** → **Create project**:

| | |
|---|---|
| Name | `wuwa-inventory-vision` |
| Storage path | an empty folder, such as `/volume1/docker/wuwa-inventory-vision`. The data is kept there; keep it out of anything that syncs from a PC (a database must not be synced while it is written) |
| Compose configuration | paste the whole of `docker-compose.yaml` -- from this folder, or the release page -- and, in its `TS_AUTHKEY` line, replace `tskey-auth-PUT-YOURS-HERE` with your key |

Then **Deploy**. The Docker app pulls one image, `wuwa-inventory-vision-server`, which holds the app
and Tailscale's own programs, and starts it as one container.

Elsewhere, with plain Docker: put `docker-compose.yaml` in a folder, put the key in a `.env`
beside it (`.env.example` says how), and run `docker compose up -d` there.

## 3. Open it

On a phone or PC signed in to your tailnet, open `http://wuwa-server.<your tailnet>.ts.net:4000`.
The app listens on `127.0.0.1` only and publishes no port: Tailscale's Serve, set in the compose
file, is the only way in, for your own devices -- **never** `funnel`, which would put it on the
internet.

In the Tailscale admin console you will find the new device, `wuwa-server`. Turn **key expiry**
off for it, or it asks to log in again in six months.

## 4. Fetch the catalogue (the first time)

A server started from nothing has no catalogue yet: no item names, pictures, recipes or builds.
Open its **更新** page and press **从 Wiki 更新**; it downloads Kuro's official catalogue (a few
minutes; the page shows how far it is). Scanners take it from the server before every scan, so do
this before the first scan. A server started from a copy of another's data (`seed-data`, below)
already has it.

## 5. Connect a scanner

The key a scanner needs is `server.key` in the `data` folder inside the storage path (made on
the first start). Download it with the NAS's file manager to the PC with the *scanner* package --
it lands in Downloads -- then double-click `2 连接服务器 Connect server` and press Enter at both
questions: Enter takes `wuwa-server` for the address and the newest `server*.key` in Downloads for the
key. Or run:

```
uv run python -m wuwa_vision server set wuwa-server <the key>
```

A second scanner (a laptop) uses the same key.

## Updating

Press **Update** on the project in the Docker app: the newest image is pulled and the data
stays. To stay on one version, change `latest` in the compose file's `WUWA_VERSION` default to a
version (e.g. `1.1.0`). The scanner needs updating only when a release changed it: 总览 says
so, and **更新 › 数据 › 版本** lists what each version changed on which side.

## Moving to one container

A server set up with the older compose file has three containers: `…-net-1`, `…-tailscale-1` and `…-wuwa-1`. It keeps running and its updates keep working, but a restart can fail with a "network namespace" error. To move:

1. Press **Update** first, so the new image is on the NAS: an older one has no Tailscale inside, and the server would drop off your tailnet.
2. **Stop the project** in the Docker app. The old Tailscale must not run beside the new one: they would fight over one device.
3. Paste the new `docker-compose.yaml` over the old one, writing your own name back over `wuwa-server` if you changed it, and **deploy**.
4. Delete the two containers left over, `…-net-1` and `…-tailscale-1`.

The data and the name on your tailnet stay, and no new key is needed.

## Trying a new version beside the one you have

A second server does not disturb the first. Create a second project -- its own name, such as
`wuwa-inventory-vision-test`, and its own empty folder -- with the same compose file, and change
one word in it: `wuwa-server` in the `TS_HOSTNAME` line, to `wuwa-server-test`. It is a second device
on your tailnet with its own data. Start it from a copy of the first server's `data` folder, put in
a `seed-data` folder inside its storage path, and it begins with everything the first has. A
scanner tries it with `server set` and its address, and goes back the same way.

Coming from the server built from source (`docs/nas.md` in the *full* package, its image called
`wuwa-vision-server`)? The same: try it beside the old one first. Changing the image line's default
to `wuwa-vision-server` and the version's to `latest` even runs it on the image your NAS already
built (`WUWA_IMAGE=wuwa-vision-server` in a `.env`, with plain Docker).

## Backing up

Everything is in the `data` folder inside the storage path: `wuwa.sqlite`, `icons/`,
`catalogue/` and `server.key`. Stop the project first for a consistent copy of the database.
`tailscale-state/` is this server's Tailscale login.

## If something is wrong

| | |
|---|---|
| The address does not open | the Tailscale container's log says whether it logged in: a key left as `tskey-auth-PUT-YOURS-HERE`, or one already used up, will not do. The device must show as connected in the Tailscale admin console |
| It asks to log in again after months | key expiry is on for this device: turn it off in the admin console and redeploy |
| A scanner's `server set` says 钥匙 | the key is not this server's: it is the line in `data/server.key` |
| A scan says the versions differ | the scanner and the server must be the same version: update both |
| After an update it will not start: "joining network namespace of container: No such container" | the project still has the older three containers, and the one holding their network was replaced. Stop the project and deploy it again (recreate: start and restart do not repair it). The data is in the project's `data` folder and is not touched. Then move to one container (above) |
| "cannot join network namespace of a non running container" | the older three containers were started or restarted at the same moment. Stop the project and deploy it again, then move to one container (above) |

The source, and the other packages: <https://github.com/oguessyky/wuwa-inventory-vision>.

Licence: Apache 2.0 ([LICENSE](LICENSE), [NOTICE](NOTICE)); how the project asks to be used:
[TERMS.md](TERMS.md); privacy: [PRIVACY.md](PRIVACY.md). An unofficial fan-made tool, not
affiliated with Kuro Games ([CREDITS.md](CREDITS.md)).
