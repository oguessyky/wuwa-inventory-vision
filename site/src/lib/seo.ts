// What the help site tells a search engine (D222). The user, 2026-10-27: "do include proper SEO
// for search engine". Every page: its own title and description, its one address, the same page
// in the other language, a card for when it is shared, and the language it is written in (one
// root layout per language). Google's Search Console tag (D214) is on all of them.
import type { Metadata, Viewport } from 'next';
import type { Lang } from './content';

export const SITE = 'https://oguessyky.github.io/wuwa-inventory-vision';
const BASE = process.env.NEXT_PUBLIC_BASE_PATH || '';
export const NAME = { zh: '鸣潮背包识别', en: 'WuWa Inventory Vision' };

/** What every page carries, whichever language's root it is under. */
export const ROOT_METADATA: Metadata = {
  metadataBase: new URL(`${SITE}/`),
  applicationName: NAME.en,
  verification: { google: 'AqQQUjncIGVuVD3R_KTd3kd9AgV9BQuQMmdkbDTu-Bs' },
  robots: { index: true, follow: true },
  formatDetection: { telephone: false, email: false, address: false },
  icons: { icon: `${BASE}/favicon.svg` },
};
export const VIEWPORT: Viewport = { themeColor: '#0b0c10', colorScheme: 'dark' };

/** The words people search for it by, in each language. */
const KEYWORDS = {
  zh: ['鸣潮', '鸣潮背包', '鸣潮库存', '鸣潮养成计算器', '鸣潮材料计算', '鸣潮突破材料', '鸣潮规划', '共鸣者养成',
       '背包识别', '库洛', 'Wuthering Waves'],
  en: ['Wuthering Waves', 'WuWa', 'inventory tracker', 'material calculator', 'ascension materials',
       'resonator planner', 'weapon planner', 'farming planner', 'screen reader', '鸣潮'],
};

/** A description as a search result shows it: the page's first lines as plain text, ended at a
 * sentence when one ends close to the limit. */
export function describe(markdown: string, most = 160): string {
  const plain = markdown
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '')            // pictures
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')          // [words](link) -> words
    .replace(/<([^>\s]+)>/g, '$1')                    // <https://...>
    .replace(/[*`#]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
  if (plain.length <= most) return plain;
  const cut = plain.slice(0, most);
  const stop = Math.max(cut.lastIndexOf('。'), cut.lastIndexOf('. '), cut.lastIndexOf('；'), cut.lastIndexOf('！'));
  return stop > most * 0.5 ? cut.slice(0, stop + 1).trim() : `${cut.replace(/\s+\S*$/, '')}…`;
}

/** One page's metadata: `paths` is its address in each language, as the site writes it. */
export function pageMetadata(lang: Lang, paths: Record<Lang, string>, title: string, description: string): Metadata {
  const url = (path: string) => `${SITE}${path}`;
  const shot = `${SITE}/screens/${lang === 'en' ? 'en/' : ''}dashboard.png`;
  const alt = lang === 'en' ? 'The dashboard: currency, scans, what to farm and buy next' : '总览：钱包、扫描、下一步该刷什么、买什么';
  return {
    title,
    description,
    keywords: KEYWORDS[lang],
    alternates: {
      canonical: url(paths[lang]),
      languages: { 'zh-CN': url(paths.zh), en: url(paths.en), 'x-default': url(paths.zh) },
    },
    openGraph: {
      type: 'website',
      siteName: NAME[lang],
      title,
      description,
      url: url(paths[lang]),
      locale: lang === 'en' ? 'en_US' : 'zh_CN',
      alternateLocale: [lang === 'en' ? 'zh_CN' : 'en_US'],
      images: [{ url: shot, width: 1400, height: 880, alt }],
    },
    twitter: { card: 'summary_large_image', title, description, images: [shot] },
  };
}

/** Structured data for a <script type="application/ld+json">, safe inside the page's HTML. */
export function ld(data: object): string {
  return JSON.stringify(data).replace(/</g, '\\u003c');
}
