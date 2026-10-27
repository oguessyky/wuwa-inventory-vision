import Link from 'next/link';
import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import { address, downloads, guideWords, packages, pages, title, words, type Lang } from '@/lib/content';
import { Markdown } from './Markdown';
import { DownloadLink } from './Download';
import { Icon } from './Icons';

export const BASE = process.env.NEXT_PUBLIC_BASE_PATH || '';
export const REPO = 'https://github.com/oguessyky/wuwa-inventory-vision';
const T = {
  zh: { site: '鸣潮背包识别', download: '下载', other: 'English', menu: '目录', prev: '上一页', next: '下一页', colon: '：',
        foot: '非官方的爱好者工具，与库洛游戏无关。《鸣潮》中的一切名称和图片都属于库洛游戏。', source: '源码',
        title: '鸣潮背包识别 · 滚一遍背包，剩下的交给它',
        guide: '看图文指南', guides: '全部指南', zip: '下载' },
  en: { site: 'WuWa Inventory Vision', download: 'Download', other: '中文', menu: 'Contents', prev: 'Previous', next: 'Next', colon: ': ',
        foot: 'An unofficial fan-made tool, not affiliated with Kuro Games. Every name and picture from Wuthering Waves belongs to Kuro Games.', source: 'Source',
        title: 'WuWa Inventory Vision · Scroll your bag once, it does the counting',
        guide: 'Open the guide', guides: 'All guides', zip: 'Download' },
};
const DESCRIPTION = {
  zh: '从屏幕读出鸣潮背包，算出下一步该刷什么：安装、使用和排错。',
  en: 'Reads your Wuthering Waves bag off the screen and works out what to farm next: how to install it, use it, and fix it.',
};

/** Each page's icon, from the app's family: the app's own drawings, and the site's five. */
const PAGE_ICON: Record<string, string> = {
  install: 'pc', home: 'nas', mac: 'laptop', guides: 'planner', scan: 'inventory', pages: 'dashboard',
  update: 'update', troubleshooting: 'help', safety: 'privacy',
};
const PageIcon = ({ slug, on = false }: { slug: string; on?: boolean }) => (slug === 'index'
  ? <img className="i logo" src={`${BASE}/favicon.svg`} alt="" width={24} height={24} />
  : <Icon name={`${PAGE_ICON[slug] ?? 'about'}${on ? '-on' : ''}`} />);

export function docMetadata(lang: Lang, slug: string): Metadata {
  const t = T[lang];
  return {
    title: slug === 'index' ? t.title : `${title(words(lang, slug))} · ${t.site}`,
    description: DESCRIPTION[lang],
    icons: { icon: `${BASE}/favicon.svg` },
  };
}

/** The site's frame (D210): header, footer, and -- on a page of the menu -- the menu beside it.
 * The landing page (D214) has the frame without the menu, the whole width its own. */
export function Frame({ lang, slug, other, children }: { lang: Lang; slug?: string; other?: string; children: ReactNode }) {
  const t = T[lang];
  const otherLang: Lang = lang === 'en' ? 'zh' : 'en';
  return (
    <div className="site" lang={lang === 'en' ? 'en' : 'zh-CN'}>
      <header className="top">
        <Link className="brand" href={address(lang, 'index')}>
          <img src={`${BASE}/favicon.svg`} alt="" width={28} height={28} /><span>{t.site}</span>
        </Link>
        <nav className="acts">
          <Link className="dl" href={`${address(lang, 'index')}#download`}>{t.download}</Link>
          <Link className="lang" href={other ?? address(otherLang, slug ?? 'index')} hrefLang={otherLang === 'en' ? 'en' : 'zh-CN'}>{t.other}</Link>
          <a className="gh" href={REPO} target="_blank" rel="noopener noreferrer">GitHub</a>
        </nav>
      </header>
      {slug ? (
        <div className="body">
          <nav className="menu" aria-label={t.menu}>
            {pages().map(p => (
              <Link key={p.slug} href={address(lang, p.slug)} className={p.slug === slug ? 'on' : ''}
                    aria-current={p.slug === slug ? 'page' : undefined}><PageIcon slug={p.slug} on={p.slug === slug} /><span>{p[lang]}</span></Link>
            ))}
          </nav>
          <main className="doc">{children}</main>
        </div>
      ) : children}
      <footer className="foot">
        <p>{t.foot}</p>
        <p><a href={REPO} target="_blank" rel="noopener noreferrer">{t.source}</a> · Apache 2.0</p>
      </footer>
    </div>
  );
}

/** One page of the menu: its words, and the way to the pages before and after it. */
export function Doc({ lang, slug }: { lang: Lang; slug: string }) {
  const t = T[lang];
  const list = pages();
  const at = list.findIndex(p => p.slug === slug);
  const prev = list[at - 1], next = list[at + 1];
  return (
    <Frame lang={lang} slug={slug}>
      <div className="doc-ic"><PageIcon slug={slug} on /></div>
      <Markdown text={words(lang, slug)} lang={lang} />
      {slug === 'guides' ? <Packages lang={lang} /> : null}
      <nav className="turn">
        {prev ? <Link href={address(lang, prev.slug)}>‹ {t.prev}{t.colon}{prev[lang]}</Link> : <span />}
        {next ? <Link href={address(lang, next.slug)}>{t.next}{t.colon}{next[lang]} ›</Link> : <span />}
      </nav>
    </Frame>
  );
}

/** Where a package's own guide is on the site: an illustrated one as it ships, a Mac one as a page. */
export function guideHref(guide: string, kind: string, lang: Lang): string {
  return guide.endsWith('.html') ? `${BASE}/guides/${kind}.html` : `${lang === 'en' ? '/en' : ''}/guides/${kind}/`;
}

/** Every package, what it is for, and its own guide -- the START-HERE in its zip (D214). */
export function Packages({ lang }: { lang: Lang }) {
  const t = T[lang];
  const zips = downloads();
  return (
    <ul className="pkgs">
      {packages().map(p => {
        const href = guideHref(p.guide, p.kind, lang);
        const name = <><b>{p[lang]}</b><code>{p.kind}</code></>;
        return (
          <li key={p.kind} id={p.kind}>
            <div className="pkg-n">{name}</div>
            <p>{lang === 'en' ? p.for_en : p.for_zh}</p>
            <div className="pkg-a">
              <DownloadLink className="zip" href={zips[p.kind].url}>{t.zip} <code>{zips[p.kind].file}</code></DownloadLink>
              {!href.endsWith('.html')
                ? <Link className="go" href={href}>{t.guide} ›</Link>
                : <a className="go" href={href}>{t.guide} ›</a>}
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export const guidesLabel = (lang: Lang) => T[lang].guides;

/** A Mac package's guide as a page of the site, in the frame of either language (D214). */
export function MacGuide({ lang, kind }: { lang: Lang; kind: string }) {
  const p = packages().find(x => x.kind === kind)!;
  const t = T[lang];
  return (
    <Frame lang={lang} slug="guides" other={`${lang === 'en' ? '' : '/en'}/guides/${kind}/`}>
      <p className="crumb"><Link href={address(lang, 'guides')}>‹ {t.guides}</Link></p>
      <article lang="en"><Markdown text={guideWords(p.guide)} lang={lang} /></article>
    </Frame>
  );
}

export const macKinds = () => packages().filter(p => p.guide.endsWith('.md')).map(p => p.kind);
