import Link from 'next/link';
import type { Metadata } from 'next';
import { address, pages, title, words, type Lang } from '@/lib/content';
import { Markdown } from './Markdown';

const BASE = process.env.NEXT_PUBLIC_BASE_PATH || '';
const REPO = 'https://github.com/oguessyky/wuwa-inventory-vision';
const T = {
  zh: { site: '鸣潮背包识别', download: '下载', other: 'English', menu: '目录', prev: '上一页', next: '下一页', colon: '：',
        foot: '非官方的爱好者工具，与库洛游戏无关。《鸣潮》中的一切名称和图片都属于库洛游戏。', source: '源码' },
  en: { site: 'WuWa Inventory Vision', download: 'Download', other: '中文', menu: 'Contents', prev: 'Previous', next: 'Next', colon: ': ',
        foot: 'An unofficial fan-made tool, not affiliated with Kuro Games. Every name and picture from Wuthering Waves belongs to Kuro Games.', source: 'Source' },
};

export function docMetadata(lang: Lang, slug: string): Metadata {
  const t = T[lang];
  const name = title(words(lang, slug));
  return {
    title: slug === 'index' ? t.site : `${name} · ${t.site}`,
    description: lang === 'en'
      ? 'Reads your Wuthering Waves bag off the screen and works out what to farm next: how to install it, use it, and fix it.'
      : '从屏幕读出鸣潮背包，算出下一步该刷什么：安装、使用和排错。',
    icons: { icon: `${BASE}/favicon.svg` },
  };
}

/** One page of the site: the frame (header, menu, footer) around its words (D210). */
export function Doc({ lang, slug }: { lang: Lang; slug: string }) {
  const t = T[lang];
  const list = pages();
  const at = list.findIndex(p => p.slug === slug);
  const prev = list[at - 1], next = list[at + 1];
  const other: Lang = lang === 'en' ? 'zh' : 'en';
  return (
    <div className="site" lang={lang === 'en' ? 'en' : 'zh-CN'}>
      <header className="top">
        <Link className="brand" href={address(lang, 'index')}>
          <img src={`${BASE}/favicon.svg`} alt="" width={28} height={28} /><span>{t.site}</span>
        </Link>
        <nav className="acts">
          <a className="dl" href={`${REPO}/releases/latest`} target="_blank" rel="noopener noreferrer">{t.download}</a>
          <Link className="lang" href={address(other, slug)} hrefLang={other === 'en' ? 'en' : 'zh-CN'}>{t.other}</Link>
          <a className="gh" href={REPO} target="_blank" rel="noopener noreferrer">GitHub</a>
        </nav>
      </header>
      <div className="body">
        <nav className="menu" aria-label={t.menu}>
          {list.map(p => (
            <Link key={p.slug} href={address(lang, p.slug)} className={p.slug === slug ? 'on' : ''}
                  aria-current={p.slug === slug ? 'page' : undefined}>{p[lang]}</Link>
          ))}
        </nav>
        <main className="doc">
          <Markdown text={words(lang, slug)} lang={lang} />
          <nav className="turn">
            {prev ? <Link href={address(lang, prev.slug)}>‹ {t.prev}{t.colon}{prev[lang]}</Link> : <span />}
            {next ? <Link href={address(lang, next.slug)}>{t.next}{t.colon}{next[lang]} ›</Link> : <span />}
          </nav>
        </main>
      </div>
      <footer className="foot">
        <p>{t.foot}</p>
        <p><a href={REPO} target="_blank" rel="noopener noreferrer">{t.source}</a> · Apache 2.0</p>
      </footer>
    </div>
  );
}
