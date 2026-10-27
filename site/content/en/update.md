# Updating

There are two things to update: the **catalogue** (the new items and characters of each game update) and **the program itself**.

## After a game update: the catalogue

On **Update → Catalogue**, press **Update from the wiki**. It downloads what is new from Kuro's official wiki: items, pictures, recipes and characters, only the new ones. The page shows which step it is on and about how long is left.

With a home, update it on the home only: scanners take the newest catalogue from the home before every scan.

The first download (a new home) takes a while; after that only what is new is fetched, which is much quicker.

## Updating the program

### The home (NAS)

In the NAS's Docker app, press **Update** on the `wuwa-inventory-vision` project: the newest image is pulled, and the data stays.

### A scanner

Not every version needs a new scanner: some change only the home. Before each scan the scanner asks the home and tells you either:

- "the home is newer, but nothing changed on the scanner's side: no need to update"; or
- "update the scanner", and what it is missing.

When it should, double-click **`4 更新 Update`** in the scanner's folder. It acts only when the home is newer and changed the scanner's side: it downloads **the home's version** from this project's GitHub releases, checks it against the release's checksums, puts it over the same folder (your `data` stays), and sets it up again.

The home's **Update → Data → Versions** lists what each version changed on which side, and the **Overview** says when a scanner should update.

### One PC only (full)

Download the new version, unzip it into a new folder, move the `data` folder across from the old one (your scans, names and settings are all in it), and double-click **`1 安装 Setup`** in the new folder.

## The two versions do not match?

A scanner and a home refuse to sync only when what they send each other changed between the two versions, and then they say the versions differ. Update both to the same version. Otherwise, different versions sync as usual.
