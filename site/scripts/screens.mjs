// The README's pictures are the site's too (D209, D210): docs/screens is copied into public/
// before a build, so there is one set of pictures, retaken by e2e/screens.
import { cpSync, existsSync, rmSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const from = join(here, '..', '..', 'docs', 'screens');
const to = join(here, '..', 'public', 'screens');
if (!existsSync(from)) throw new Error(`no pictures at ${from}`);
rmSync(to, { recursive: true, force: true });
cpSync(from, to, { recursive: true });
console.log(`pictures: ${from} -> ${to}`);
