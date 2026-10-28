// Each package's own guide (D214), the one its zip carries as START-HERE: deploy/release/guides/
// *.html is copied into public/guides/ before a build, {version} filled in as tools/make_release.py
// does, with a way back to the site added at the top. The Mac guides (.md) are pages of the site.
import { existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..', '..');
const from = join(root, 'deploy', 'release', 'guides');
const to = join(here, '..', 'public', 'guides');
if (!existsSync(from)) throw new Error(`no guides at ${from}`);
const version = /^version\s*=\s*"([^"]+)"/m.exec(readFileSync(join(root, 'pyproject.toml'), 'utf-8'))?.[1];
if (!version) throw new Error('no version in pyproject.toml');

// back to the page that shows this guide's steps (D219): full on the install page, the rest on the server's
const page = { full: 'install', 'mac-full': 'mac', 'mac-scanner': 'mac' };
const back = name => `<a href="../${page[name.replace(/\.html$/, '')] ?? 'server'}/" style="display:inline-block;`
  + 'margin:0 0 8px;color:#e8c15b;font-size:14px;text-decoration:none">‹ 返回帮助网站 · Back to the help site</a>';
rmSync(to, { recursive: true, force: true });
mkdirSync(to, { recursive: true });
for (const name of readdirSync(from).filter(n => n.endsWith('.html'))) {
  const page = readFileSync(join(from, name), 'utf-8').replaceAll('{version}', version)
    .replace(/<main>/, `<main>${back(name)}`);
  writeFileSync(join(to, name), page);
}
console.log(`guides: ${from} -> ${to} (v${version})`);
