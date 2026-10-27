# Updating

Two things update: the **catalogue** (the game's new items and resonators) and the **program**.

## After a game update: the catalogue

**Update → Catalogue → Update from the wiki**. Only what is new is fetched; the page shows how far it is and how long is left. With a home, update it there only: a scanner takes it from the home before each scan.

## The program

| You use | How to update |
|---|---|
| A home (NAS) | **Update** on the project in the Docker app; the data stays |
| A scanner | When the dashboard says so, double-click **`4 更新 Update`** |
| One PC (full) | Unzip the new version to a new folder, move the old `data` over, double-click **`1 安装 Setup`** |

Not every version changes the scanner: some change only the home. A scanner asks the home before each scan, and **Update → Data → Versions** lists which side each version changed.

`4 更新 Update` does something only when the home is newer and has a change for the scanner: it downloads the home's version from this project's GitHub, checks its checksums, and leaves `data` alone.

## The two sides disagree?

Only when the format they sync in changed do they refuse, saying the versions differ. Update both to the same version.
