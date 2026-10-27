# A home on a NAS

The **home** is a machine that is always on (a NAS, a mini PC). It keeps the data and shows the pages. The PC with the game only scans, and sends each tab to the home as it is done. Your phone opens it anytime, with the PC off too.

You need:

- a NAS with Docker and Compose (UGREEN UGOS, Synology, Unraid, QNAP…) or any Linux machine;
- a free [Tailscale](https://tailscale.com) account.

Nothing to build and no commands on the NAS: copy the configuration below and paste it into the Docker app. The home is only on your own Tailscale network, never on the internet.

{{steps}}

## Backup

Everything is in the `data` folder in the storage path: `wuwa.sqlite`, `icons/`, `catalogue/`, `home.key`. Stop the project before copying it.

## Next

- [How to scan](/scan), [Updating](/update).
- Stuck? [Troubleshooting](/troubleshooting).
