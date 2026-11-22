// What each version on 版本记录 offers to download (version downloads): its packages as they were
// released, its server image, the servers its scanner was made with and every server it also
// syncs with -- or, for a version marked off by hand, why, and which to take instead.
// Pure: no files read, so tests/test_version_downloads.py runs it with Node on releases.json.

export interface Change { zh: string; en: string }
export interface Release {
  version: string; date: string; scanner: Change[]; home: Change[];
  /** why this one is not offered, and the version to take instead */
  no_download?: { use: string; zh: string; en: string };
  /** the oldest server its scanner syncs with (tools/sync_pairs.py); left out: every server */
  needs_server?: string;
}
export interface VersionFile { kind: string; file: string; url: string }
export type Offer =
  | { version: string; offered: true; files: VersionFile[]; sums: string; image: string | null;
      madeWith: { from: string; to: string }; alsoFrom: string }
  | { version: string; offered: false; use: string; zh: string; en: string };

const REPO = 'https://github.com/oguessyky/wuwa-inventory-vision';

const parts = (v: string): number[] => v.split('.').map(Number);
/** a < b: -1, equal: 0, a > b: 1 */
export function compare(a: string, b: string): number {
  const [x, y] = [parts(a), parts(b)];
  for (let i = 0; i < Math.max(x.length, y.length); i++) {
    const d = (x[i] ?? 0) - (y[i] ?? 0);
    if (d) return d < 0 ? -1 : 1;
  }
  return 0;
}

/** The packages a version was released with, as GitHub has them (checked when this was made):
 * 1.0.x sit together in the `old-versions` release; the server's zip was `home` until 1.2.0;
 * the Mac packages began at 1.1.1; the server image, at 1.2.0. */
function files(v: string): { files: VersionFile[]; sums: string; image: string | null } {
  const old = compare(v, '1.1.0') < 0;
  const at = `${REPO}/releases/download/${old ? 'old-versions' : `v${v}`}`;
  const kinds = ['full', 'scanner', compare(v, '1.2.0') < 0 ? 'home' : 'server'];
  if (compare(v, '1.1.1') >= 0) kinds.push('mac-full', 'mac-scanner');
  return {
    files: kinds.map(kind => {
      const file = `wuwa-inventory-vision-${v}-${kind}.zip`;
      return { kind, file, url: `${at}/${file}` };
    }),
    sums: `${at}/${old ? `SHA256SUMS-${v}.txt` : 'SHA256SUMS.txt'}`,
    image: compare(v, '1.2.0') >= 0 ? v : null,
  };
}

export function offer(releases: Release[], version: string): Offer {
  const r = releases.find(x => x.version === version);
  if (!r) throw new Error(`no release ${version}`);
  if (r.no_download) return { version, offered: false, ...r.no_download };
  const oldestFirst = [...releases].sort((a, b) => compare(a.version, b.version));
  const at = oldestFirst.findIndex(x => x.version === version);
  // made with: from the release that last changed the scanner, to the one before the next that
  // does -- the servers released while this scanner was the same code (the newest, at the end)
  let from = at;
  while (from > 0 && !oldestFirst[from].scanner.length) from--;
  let to = at;
  while (to + 1 < oldestFirst.length && !oldestFirst[to + 1].scanner.length) to++;
  return {
    version, offered: true, ...files(version),
    madeWith: { from: oldestFirst[from].version, to: oldestFirst[to].version },
    alsoFrom: r.needs_server ?? oldestFirst[0].version,
  };
}
