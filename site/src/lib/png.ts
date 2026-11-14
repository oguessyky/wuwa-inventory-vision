// A picture's size, read at build from its PNG's header (D294): a guide puts a narrow screenshot
// beside its words and a wide one across the page. The pictures are docs/screens', copied into
// public/ before a build (scripts/screens.mjs); none is read in a browser.
import { existsSync, openSync, readSync, closeSync } from 'node:fs';
import { join } from 'node:path';

const PLACES = [join(process.cwd(), 'public'), join(process.cwd(), '..', 'docs')];

/** Width and height of `screens/….png`, or null when it is not a PNG found here. */
export function pngSize(src: string): { width: number; height: number } | null {
  const file = PLACES.map(dir => join(dir, src)).find(existsSync);
  if (!file || !/\.png$/i.test(file)) return null;
  const head = Buffer.alloc(24);
  const fd = openSync(file, 'r');
  try { readSync(fd, head, 0, 24, 0); } finally { closeSync(fd); }
  if (head.toString('ascii', 12, 16) !== 'IHDR') return null;
  return { width: head.readUInt32BE(16), height: head.readUInt32BE(20) };
}
