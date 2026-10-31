# A server on a NAS

The **server** is a machine that is always on (a NAS, a mini PC). It keeps the data and shows the pages. The PC with the game only scans, and sends each tab to the server as it is done. Your phone opens it anytime, with the PC off too.

You need:

- a NAS with Docker and Compose (UGREEN UGOS, Synology, Unraid, QNAP…) or any Linux machine;
- a free [Tailscale](https://tailscale.com) account.

Nothing to build and no commands on the NAS: copy the configuration below and paste it into the Docker app. The server is only on your own Tailscale network, never on the internet.

{{steps}}

## Moving to one container

A server set up with the older compose file has three containers: `…-net-1`, `…-tailscale-1` and `…-wuwa-1`. It keeps running and its updates keep working, but a restart can fail with a "network namespace" error. One container has nothing to fail that way. To move:

1. Press **Update** first, so the new image is on the NAS: an older one has no Tailscale inside, and the server would drop off your tailnet.
2. **Stop the project** in the Docker app. The old Tailscale must not run beside the new one: they would fight over one device.
3. Paste the new `docker-compose.yaml` over the old one, writing your own name back over `wuwa-server` if you changed it, and **deploy**.
4. Delete the two containers left over, `…-net-1` and `…-tailscale-1`.

The data and the name on your tailnet stay, and no new key is needed.

## Backup

Everything is in the `data` folder in the storage path: `wuwa.sqlite`, `icons/`, `catalogue/`, `server.key`. Stop the project before copying it.

## Next

- [How to scan](/scan), [Updating](/update).
- Stuck? [Troubleshooting](/troubleshooting).
