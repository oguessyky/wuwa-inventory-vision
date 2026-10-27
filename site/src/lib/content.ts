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
