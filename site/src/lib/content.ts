// The site's words (D210): site/content/pages.json lists the pages in menu order, and each has
// content/zh/<slug>.md and content/en/<slug>.md. Read when the site is built, never in a browser.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

export type Lang = 'zh' | 'en';
export interface Page { slug: string; zh: string; en: string }

const CONTENT = join(process.cwd(), 'content');

export function pages(): Page[] {
  return JSON.parse(readFileSync(join(CONTENT, 'pages.json'), 'utf-8')).pages;
}

export function words(lang: Lang, slug: string): string {
  return readFileSync(join(CONTENT, lang, `${slug}.md`), 'utf-8');
}

/** A page's address on the site, in a language: '/', '/install/', '/en/', '/en/install/'. */
export function address(lang: Lang, slug: string): string {
  const path = slug === 'index' ? '/' : `/${slug}/`;
  return lang === 'en' ? `/en${path}` : path;
}

/** The page's title: its one `# ` line. */
export function title(text: string): string {
  return /^# (.*)$/m.exec(text)?.[1] ?? '';
}

export interface Package { kind: string; zh: string; en: string; for_zh: string; for_en: string; guide: string }

/** The packages and each one's own guide (D214): site/content/packages.json. */
export function packages(): Package[] {
  return JSON.parse(readFileSync(join(CONTENT, 'packages.json'), 'utf-8')).packages;
}

const ROOT = join(process.cwd(), '..');
const REPO_FILE = 'https://github.com/oguessyky/wuwa-inventory-vision/blob/main/';

/** The release's version, as the packages carry it. */
export function version(): string {
  return /^version\s*=\s*"([^"]+)"/m.exec(readFileSync(join(ROOT, 'pyproject.toml'), 'utf-8'))?.[1] ?? '';
}

/** A Mac package's guide (deploy/release/mac-*.md), as its zip has it: the version filled in, and
 * a link to a file beside it in the zip (PRIVACY.md) sent to that file in the repository. */
export function guideWords(file: string): string {
  return readFileSync(join(ROOT, 'deploy', 'release', file), 'utf-8')
    .replaceAll('{version}', `v${version()}`)
    .replace(/\]\(((?!https?:|\/|#)[^)]+)\)/g, (_, rel: string) => `](${REPO_FILE}${rel})`);
}

export interface Download { kind: string; file: string; url: string }

/** Each package's zip itself (D214): the site is built with every release, so this version's files.
 * Named as tools/make_release.py names them; the releases page is for anyone who wants more. */
export function downloads(): Record<string, Download> {
  const v = version();
  const repo = 'https://github.com/oguessyky/wuwa-inventory-vision';
  return Object.fromEntries(packages().map(({ kind }) => {
    const file = `wuwa-inventory-vision-${v}-${kind}.zip`;
    return [kind, { kind, file, url: `${repo}/releases/download/v${v}/${file}` }];
  }));
}
