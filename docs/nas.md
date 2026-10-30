# The dashboard on a NAS

The app can live in two places at once: the **server**, a box that is always on, which holds the
data and shows the dashboard to every device on your tailnet; and one or more **scanners**, the
machines with the game, which read the bag and send what they read to the server.

One machine on its own is still the default and needs none of this ([setup](setup.md)).

```
   scanner (PC with the game)                     server (the NAS)
   ──────────────────────────                     ──────────────
   before a scan:   fetch what the server knows  ◀──  learned icons, names given on a phone,
                                                    the pull history, the catalogue
   during a scan:   each tab once finished     ──▶  added to what is there
   after a scan:    whatever is left           ──▶  added to what is there
```

- **A tab goes server once it is finished** -- left with the game's count reached -- while the
  scan goes on (D173); the rest when the scan ends. A network drop costs nothing: what could
  not be handed over is kept and sent later, at the end or with the next scan. Going back to a
  finished tab carries on with it, and it is sent again when left finished.
- **No screenshot ever leaves the scanner.** What is sent is the list of items and counts, and
  the small tile pictures cut from inside the grid.
- **The server recognises nothing.** No GPU, no model: it shows what scanners send. So anything
  that needs the game (scanning) is done at the PC, and everything else — looking things up,
  fixing a count, setting targets, 从 Wiki 更新, 手动修改 — works from a phone.
- **Viewing and editing have no login**, as on a desktop: anyone on your tailnet can use every
  button. **Uploading a scan needs a key**, so only a scanner you set up can add to the data.

## Two ways to set a server up

- **Ready-made** (D183, D186, the easy one): one compose file that runs the published image
  (amd64 and arm64) with Tailscale beside it, pasted into the NAS's Docker app -- Project ->
  Create project, named `wuwa-inventory-vision`, an empty folder, the file with your Tailscale
  key in it, deploy. No build, no SSH, no script, no zip; the *server* package's `START-HERE.html`
  shows each step, and the Docker app's **update** button brings each new version. That Tailscale joins your tailnet as a device of its
  own; one already on the NAS is not touched.
- **Built from source** (below): the app laid out from the repository and built on the NAS. For
  trying changes before a release, or a NAS that already runs Tailscale and should share it.

A second server of either kind runs beside the first without disturbing it: its own folder, its
own data, its own name on the tailnet. That is how a new version is tried.

## What you need (built from source)

- A NAS (or any always-on Linux box) with Docker and Docker Compose.
- [Tailscale](https://tailscale.com) on it, signed in to your tailnet.
- A folder the NAS can see from your PC: a network share, or a folder that syncs to it.

## 1. Put the app where the NAS can build it

On the PC, in the repository:

```bash
uv run python tools/make_nas_bundle.py "<the folder the NAS can see>" --seed
```

That writes `docker-compose.yaml`, `setup.sh`, `.env.example`, `app/` (the source the image is built
from) and, with `--seed`, `seed-data/` — a first copy of your database, scan crops and catalogue
(about 80 MB). It touches nothing else in that folder. Add `--check` to see what it would do
first.

## 2. Say where the data lives

In that folder, make a file called `.env` with one line — a folder on the NAS for the data:

```
WUWA_DATA=/volume1/docker/wuwa-vision-data
```

**Not the folder that syncs from your PC**: a database must not be synced while it is being
written. Leave the line out and the data goes in a Docker volume instead.

The same file takes `WUWA_IMAGE` and `WUWA_CONTAINER` if you name things your own way
(`.env.example` lists everything).

## 3. Set it up

On the NAS (SSH), in that folder:

```bash
sh setup.sh
```

It says what it does as it goes:

1. **Works out the network.** The app listens on `127.0.0.1` and nothing else, and publishes no
   port: the only way in is Tailscale's own proxy, so the app has to be on the same `127.0.0.1`
   as Tailscale. The script looks at how the Tailscale container is networked and writes
   `WUWA_NETWORK` into `.env` — `host`, or `container:tailscale` when Tailscale has a network
   of its own.
2. **Builds and starts** (`docker compose up -d --build`). The first build downloads Python
   packages and takes a few minutes. On its first start the server takes in `seed-data/`; from
   then on its own copy is the one that counts, and you can delete `seed-data/`.
3. **Serves it to your tailnet**, once: `tailscale serve --bg --http=4000 http://127.0.0.1:4000`.
   `--bg` keeps it across restarts. This is `serve`, which reaches your own tailnet only — never
   `funnel`, which would put it on the internet.
4. **Prints the address to open and the command for the PC**, key included.

If your Tailscale container is not called `tailscale`: `TAILSCALE_CONTAINER=<its name> sh
setup.sh`. If Tailscale is installed on the NAS itself, not in Docker: `TAILSCALE_CONTAINER= sh
setup.sh`.

Open the address it printed on a phone signed in to your tailnet. Use the name (`…ts.net`), not
the `100.x` address.

## 4. Give the PC its server

On the PC, once — the line `setup.sh` printed:

```bash
uv run python -m wuwa_vision server set http://<the NAS's tailnet name>:4000 <the key>
```

(The key is the one line in `server.key` in the server's data folder, if you need it again. Leave
the key out and `server set` takes the newest `server*.key` in Downloads; give a path and it reads
that file.)
It checks the address and the key before saving them. From then on:

```bash
uv run python -m wuwa_vision live --identify
```

says where the scan is going, fetches what the server knows, scans as before, sends each tab once
it is finished, and the rest when the scan ends. While anything is crossing, one line in the terminal draws over itself -- a bar,
what is left, and how fast it is going:

```
  to server   [#######-------------]  37%  5.3 MB left of 8.4 MB  2.3 MB/s  (2 scan(s), 214 crop(s))
  from server [##############------]  70%  12 of 40 crops left  95 KB/s
```

The same is on the scan's live page and, with `--share`, on your phone. The speed is the
transfer's own (what crossed, over the time it took), on Wi-Fi or on a cable; nothing is sent to
measure it. `wuwa push` and `wuwa pull` draw the line too.

If the server does not answer, the scan still runs and is kept:

```
! server: 连不上服务器 …
  scanning on this machine's copy; the scan is kept and sent next time
```

| | |
|---|---|
| `wuwa server` | where this machine's scans go, and how many are waiting |
| `wuwa push` | send what is waiting, now |
| `wuwa pull` | fetch what the server knows, now |
| `wuwa server forget` | this machine keeps its own scans again |

(`wuwa` here is `uv run python -m wuwa_vision`.)

A second scanner — a laptop — is set up the same way, with the same key. Two scanners cannot
overwrite each other: everything is merged piece by piece, and a scan the server already has is
never added twice.

## What is the truth, when two places disagree

Both places hold the same learned data, so a scan never needs the network: before it starts,
the scanner compares its copy with the server's and takes what was added, changed or removed
there; after it ends, it sends what it added.

**The server** is the truth for anything it holds. A name given on a phone replaces what a
scanner thought; a name taken away on a phone stays away; a phantom tile dismissed on a phone
(不是物品) is removed from the scanner too, instead of being sent back. A scanner's word counts
for what the server has never seen. After a new item is named on the server, the scanner knows it
from its next scan on.

**清空扫描数据** on the server starts every scanner over too: the next time one connects, its own
copy of what scans taught is set aside (in `data/backups/`) and forgotten, or its next upload
would bring it all back.

## After a patch

- **从 Wiki 更新** on the server's 更新 page fetches the new catalogue there. Each scanner fetches
  it from the server before its next scan and embeds the new icons itself before reading
  anything (D179), so that scan already knows them. The "also rebuild the recognition gallery" switch is not shown on the
  server: it has no recogniser to rebuild with.
- **A new version of the app**: `git pull` on the PC, run step 1 again without `--seed`, then
  rebuild on the NAS -- `sh setup.sh` again, or from the NAS's own Docker app (below). A release often changes only one
  side: the server's 更新 › 数据 › 版本 lists what each changed on which side, 总览 says when a
  scanner (or the server) is missing changes of its own, and the scanner says it before each scan
  (D197). They refuse to talk only across versions that changed what is sent.

## Rebuilding from the NAS's own Docker app

The image is built on the NAS from `app/`; it is not downloaded from anywhere. So the **update**
button of a NAS's Docker app, which looks for a newer image in a registry, finds nothing. What
brings a new version in is a **rebuild of the project**.

To have that as a button:

1. Run `sh setup.sh` once, as above. It writes the network into `.env` and sets up
   `tailscale serve`; neither needs doing again.
2. In the NAS's Docker app, open its **projects** (Compose) section and add a project **in this
   same folder**, using the `docker-compose.yaml` that is already there, under the folder's own
   name. The container that is running belongs to that project and is taken over as it is.
3. From then on: copy the new version in (step 1 of the setup) and press the project's
   **rebuild** / **redeploy**. Whichever way the app brings the project up, it is rebuilt from
   `app/` (`pull_policy: build`), and takes a moment when nothing changed.

Keep the project in this folder: `app/`, `.env` and `seed-data/` are found beside the compose
file. A project the app makes somewhere else, from pasted text, would not find them.

## Moving to one container

A server set up with the older compose file has three containers: `…-net-1`, `…-tailscale-1` and `…-wuwa-1`. It keeps running and its updates keep working, but a restart can fail with a "network namespace" error. To move:

1. Press **Update** first, so the new image is on the NAS: an older one has no Tailscale inside, and the server would drop off your tailnet.
2. **Stop the project** in the Docker app (`docker compose stop` elsewhere). The old Tailscale must not run beside the new one: they would fight over one device.
3. Paste the new `docker-compose.yaml` over the old one, writing your own name back over `wuwa-server` if you changed it, and **deploy**.
4. Delete the two containers left over, `…-net-1` and `…-tailscale-1`.

The data and the name on your tailnet stay, and no new key is needed.

## Backing up

Everything the server has is in its data volume: `wuwa.sqlite`, `icons/`, `catalogue/` and
`server.key`. Stop the container or use `sqlite3 … ".backup"` for a consistent copy of the
database; the rest are plain files.

## If something is wrong

| | |
|---|---|
| The Docker app's **update** does nothing | There is no image to download; rebuild the project instead (see "Rebuilding from the NAS's own Docker app"). |
| A rebuild changed nothing | Open `http://<the NAS>:4000/api/sync/hello`: its `version` is the `app/VERSION` the running build was made from. If it is the old one while `app/VERSION` on the NAS is new, the project was restarted, not rebuilt -- rebuild it, or `sh setup.sh`. If `app/VERSION` on the NAS is old too, the copy from the PC has not finished arriving. |
| A thing is recognised as something else, scan after scan | The scanner learned a wrong name for its picture. Open 更新 › 识别 on the server, find the name (or the 可能认错 chip), click the picture and give it the right name: every crop of that picture and the scans that saw it change, and each scanner takes it at its next fetch. |
| `server set` says 连不上服务器 | The address is not answering from the PC. Open it in the PC's browser; check that `setup.sh` finished and that both are on the tailnet. |
| … says 不是服务器 | Something else answers there, or the app was started without `--home`. |
| … says 钥匙 | The key is not the one in the server's `server.key`. |
| … says the address must be on the tailnet | Only `…ts.net`, `100.x` and this machine itself are accepted — never a LAN or public address. |
| It stopped answering after the Tailscale container was updated or recreated | With `WUWA_NETWORK=container:…` the app lives in that container's network, and a new Tailscale container is a new network. Run `sh setup.sh` again. |
| A push says 清空 | The server was wiped. `wuwa pull`, then scan again. |
| A push or pull says the versions differ | Update the scanner and the server to the same version. |
| An update stops with "joining network namespace of container: No such container" | The project still has the older three containers, and the one holding their network was replaced. Stop the project and deploy it again (recreate: start and restart do not repair it); `docker compose up -d` does the same. Nothing in `data/` is touched. Then move to one container (below; D238). |
| "cannot join network namespace of a non running container" | The older three containers were started or restarted at the same moment. Stop the project and deploy it again, then move to one container (below; D238). |
| The app runs but the address does not open from a phone | `WUWA_NETWORK` in `.env` does not match how Tailscale runs, so `tailscale serve` is pointing at a different `127.0.0.1`. Delete that line and run `sh setup.sh` again. |
