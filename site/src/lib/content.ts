// The site's words (D210): site/content/pages.json lists the pages in menu order, and each has
// content/zh/<slug>.md and content/en/<slug>.md. Read when the site is built, never in a browser.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

export type Lang = 'zh' | 'en';
export type Group = 'install' | 'use' | 'help' | 'legal';
export interface Page {
  slug: string; zh: string; en: string; group?: Group; about_zh?: string; about_en?: string;
  /** a legal page's words: the repository's own files, per language (D223) */
  source?: Record<Lang, string[]>;
}

const CONTENT = join(process.cwd(), 'content');

export function pages(): Page[] {
  return JSON.parse(readFileSync(join(CONTENT, 'pages.json'), 'utf-8')).pages;
}

export function words(lang: Lang, slug: string): string {
  const page = pages().find(p => p.slug === slug);
  if (page?.source) return legalWords(lang, page);
  return readFileSync(join(CONTENT, lang, `${slug}.md`), 'utf-8');
}

/** Where each of the repository's notices is a page of the site, so a link between them stays
 * here (D223). */
const LEGAL: Record<string, string> = {
  'PRIVACY.md': 'privacy', 'PRIVACY.zh-CN.md': 'privacy', 'TERMS.md': 'terms',
  'LICENSE': 'licence', 'NOTICE': 'licence', 'CREDITS.md': 'credits',
};

/** A legal page's words (D223): the files every package carries -- PRIVACY, TERMS, CREDITS,
 * NOTICE and LICENSE -- read when the site is built, so the page is never a copy that drifts.
 * A Markdown file is the page; a plain one (LICENSE) stands where `{{text:NAME}}` is, as it is.
 * A Chinese page whose file is only in English says so above it: the English is what counts. */
export function legalWords(lang: Lang, page: Page): string {
  const about = (lang === 'en' ? page.about_en : page.about_zh) ?? '';
  const files = page.source![lang];
  if (!files.some(name => name.endsWith('.md'))) {
    const lede = lang === 'en' ? `${about}. The notice and the licence, as every package carries them.`
      : `${about}。下面是每个程序包里都带着的声明和许可原文（英文）。`;
    return [`# ${page[lang]}`, lede, ...files.map(name => `{{text:${name}}}`)].join('\n\n');
  }
  const text = readFileSync(join(ROOT, files[0]), 'utf-8').replace(/\r\n/g, '\n')
    .replace(/\]\(((?!https?:|\/|#|mailto:)[^)#]+)(#[^)]*)?\)/g, (_, rel: string, hash = '') =>
      LEGAL[rel] ? `](/${LEGAL[rel]}${hash})` : `](${REPO_FILE}${rel}${hash})`);
  if (lang === 'zh' && !/[一-鿿]/.test(title(text))) {
    // only in English: a Chinese title and a line that says so, then the English as it is
    const body = text.replace(/^# .*\n+/m, '');
    return `# ${page.zh}\n\n${about}。本页只有英文原文，以英文为准。\n\n${body}`;
  }
  return text;
}

/** One of the repository's plain-text notices (LICENSE, NOTICE), as it is. */
export function rootText(name: string): string {
  return readFileSync(join(ROOT, name), 'utf-8').replace(/\r\n/g, '\n');
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

export interface GuideStep { n: number; title: string; text: string[]; tips: string[]; picture: string }

/** A package's own guide, step by step (D219): its numbered steps with their drawings, read from
 * deploy/release/guides/<kind>.html when the site is built, so the install pages show the same
 * pictures the zip's START-HERE has. Each step's words in one language; the drawings are the
 * project's own SVG, written by tools/make_guides.py, and their labels are in both. */
export function guideSteps(kind: string, lang: Lang): GuideStep[] {
  const page = readFileSync(join(ROOT, 'deploy', 'release', 'guides', `${kind}.html`), 'utf-8')
    .replaceAll('{version}', version());
  const want = lang === 'en' ? 'en' : 'zh-CN';
  const steps: GuideStep[] = [];
  for (const m of page.matchAll(/<section class="step" id="s(\d+)">([\s\S]*?)<\/section>/g)) {
    const body = m[2];
    const title = (lang === 'en'
      ? /<small lang="en">([\s\S]*?)<\/small>/.exec(body)
      : /<span lang="zh-CN">([\s\S]*?)<\/span>/.exec(body))?.[1] ?? '';
    const paras = [...body.matchAll(/<p(?: class="(tip|warn)")? lang="([^"]+)">([\s\S]*?)<\/p>/g)]
      .filter(p => p[2] === want);
    steps.push({
      n: Number(m[1]),
      title,
      text: paras.filter(p => !p[1]).map(p => p[3]),
      tips: paras.filter(p => p[1]).map(p => p[3]),
      picture: (body.match(/<svg[\s\S]*?<\/svg>/g) ?? []).join(''),     // a step may have two (a Mac's)
    });
  }
  return steps;
}

/** The server's compose file as it ships (D219), for the step that pastes it into the NAS's Docker
 * app: read from deploy/server/ at build, so the page never holds a copy that drifts. Its opening
 * notes say what the page around it says, so it starts at `services:`. */
export function compose(): string {
  const file = readFileSync(join(ROOT, 'deploy', 'server', 'docker-compose.yaml'), 'utf-8').replace(/\r\n/g, '\n');
  return file.slice(file.indexOf('services:'));
}


export interface Release { version: string; date: string; scanner: { zh: string; en: string }[]; home: { zh: string; en: string }[] }

/** Every release and what it changed on each side (D227): the app's own list, read at build. */
export function releases(): Release[] {
  return JSON.parse(readFileSync(join(ROOT, 'src', 'wuwa_vision', 'releases.json'), 'utf-8')).releases;
}
