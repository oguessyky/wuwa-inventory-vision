// The README's pictures are the site's too (D209, D210): docs/screens is copied into public/
// before a build, so there is one set of pictures, retaken by e2e/screens. Each is shown as WebP
// (D230), made here with sharp -- 7.6 MB of PNG is about 2 MB -- and the PNG stays beside it for
// the card a shared link shows (seo.ts), which every app can draw.
import { cpSync, existsSync, readdirSync, rmSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

const here = dirname(fileURLToPath(import.meta.url));
const from = join(here, '..', '..', 'docs', 'screens');
const to = join(here, '..', 'public', 'screens');
if (!existsSync(from)) throw new Error(`no pictures at ${from}`);
rmSync(to, { recursive: true, force: true });
cpSync(from, to, { recursive: true });

let made = 0;
for (const entry of readdirSync(to, { recursive: true, withFileTypes: true })) {
  if (!entry.isFile() || !/\.(png|jpe?g)$/i.test(entry.name)) continue;
  const file = join(entry.parentPath ?? entry.path, entry.name);
  await sharp(file).webp({ quality: 82 }).toFile(file.replace(/\.(png|jpe?g)$/i, '.webp'));
  made += 1;
}
console.log(`pictures: ${from} -> ${to} (${made} as WebP)`);
