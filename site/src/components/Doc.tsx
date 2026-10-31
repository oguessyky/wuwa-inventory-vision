import Link from 'next/link';
import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import { address, guideSteps, pages, releases, rootText, title, words, type Group, type Lang } from '@/lib/content';
import { Markdown } from './Markdown';
import { GuideSteps, type Part } from './GuideSteps';
import { Icon } from './Icons';
import { Nav, type NavPage } from './Nav';
import { describe, ld, pageMetadata, SITE } from '@/lib/seo';

export const BASE = process.env.NEXT_PUBLIC_BASE_PATH || '';
export const REPO = 'https://github.com/oguessyky/wuwa-inventory-vision';
const T = {
  zh: { site: '鸣潮背包识别', download: '下载', other: 'English', next: '接下来', top: '首页',
        groups: { install: '安装', use: '使用', help: '帮助', legal: '法律' } as Record<Group, string>,
        tagline: '从屏幕读出鸣潮背包，算出下一步该刷什么。',
        foot: '非官方的爱好者工具，与库洛游戏无关。《鸣潮》中的一切名称和图片都属于库洛游戏。', source: '源码',
        title: '鸣潮背包识别 · 鸣潮背包扫描器，滚一遍背包，剩下的交给它',
        guide: '这个包的指南', zip: '下载', mac: '在 Mac 上安装' },
  en: { site: 'WuWa Inventory Vision', download: 'Download', other: '中文', next: 'Next', top: 'Home',
        groups: { install: 'Install', use: 'Use', help: 'Help', legal: 'Legal' } as Record<Group, string>,
        tagline: 'Reads your Wuthering Waves bag off the screen and works out what to farm next.',
        foot: 'An unofficial fan-made tool, not affiliated with Kuro Games. Every name and picture from Wuthering Waves belongs to Kuro Games.', source: 'Source',
        title: 'WuWa Inventory Vision · Wuthering Waves inventory scanner and planner',
        guide: 'This package’s guide', zip: 'Download', mac: 'Install on a Mac' },
};
const DESCRIPTION = {
  zh: '鸣潮背包扫描器：从屏幕读出鸣潮背包，算出下一步该刷什么。安装、使用和排错。',
  en: 'A Wuthering Waves inventory scanner: it reads your bag off the screen and works out what to farm next. How to install it, use it, and fix it.',
};

/** Each page's icon, from the app's family: the app's own drawings, and the site's five. */
const PAGE_ICON: Record<string, string> = {
  install: 'pc', server: 'nas', mac: 'laptop', scan: 'inventory', pages: 'dashboard',
  update: 'update', versions: 'update', troubleshooting: 'help', safety: 'privacy',
  privacy: 'privacy', terms: 'about', licence: 'about', credits: 'about',
};
const PageIcon = ({ slug, on = false }: { slug: string; on?: boolean }) => (slug === 'index'
  ? <img className="i logo" src={`${BASE}/favicon.svg`} alt="" width={24} height={24} />
  : <Icon name={`${PAGE_ICON[slug] ?? 'about'}${on ? '-on' : ''}`} />);

/** A page's words in their parts: the # title, the paragraph under it (the band's, and what a
 * search result shows), and the rest. */
function parts(lang: Lang, slug: string) {
  const text = words(lang, slug).replace(/\r\n/g, '\n');
  const [, rest = ''] = text.split(/^# .*$/m);
  const body = rest.replace(/^\s+/, '');
  const found = body.startsWith('#') ? 0 : body.search(/\n\s*\n/);   // a page may open on a heading
  const cut = found < 0 ? body.length : found;
  const about = pages().find(p => p.slug === slug);
  return {
    title: title(text),
    lede: body.slice(0, cut) || ((lang === 'en' ? about?.about_en : about?.about_zh) ?? ''),
    body: body.slice(cut),
  };
}

/** Each page's title, description, address in both languages and card (D222). */
export function docMetadata(lang: Lang, slug: string): Metadata {
  const t = T[lang];
  const paths = { zh: address('zh', slug), en: address('en', slug) };
  if (slug === 'index') return pageMetadata(lang, paths, t.title, DESCRIPTION[lang]);
  const page = parts(lang, slug);
  // a legal page opens on a date or a heading: its own line says better what it is (D223)
  const me = pages().find(p => p.slug === slug);
  const about = lang === 'en' ? me?.about_en : me?.about_zh;
  const said = me?.source && about ? `${about}${lang === 'en' ? '.' : '。'}` : page.lede;
  return pageMetadata(lang, paths, `${page.title} · ${t.site}`, describe(said));
}

/** The pages as the bar and the foot show them: each with its group, icon and line (D221). */
function navPages(lang: Lang): NavPage[] {
  return pages().filter(p => p.group).map(p => ({
    slug: p.slug, name: p[lang], href: address(lang, p.slug), icon: PAGE_ICON[p.slug] ?? 'about', group: p.group!,
    about: (lang === 'en' ? p.about_en : p.about_zh) ?? '',
  }));
}

/** The site's frame (D221): a bar across the top with the pages in three groups, and a foot that
 * is the site's map -- the way a product's site is, not a manual's list down the side. */
export function Frame({ lang, slug, other, children }: { lang: Lang; slug?: string; other?: string; children: ReactNode }) {
  const t = T[lang];
  const otherLang: Lang = lang === 'en' ? 'zh' : 'en';
  const list = navPages(lang);
  return (
    <div className="site" lang={lang === 'en' ? 'en' : 'zh-CN'}>
      <header className="top">
        <Link className="brand" href={address(lang, 'index')}>
          <img src={`${BASE}/favicon.svg`} alt="" width={28} height={28} /><span>{t.site}</span>
        </Link>
        <Nav lang={lang} slug={slug} pages={list} />
        <div className="acts">
          <Link className="lang" href={other ?? address(otherLang, slug ?? 'index')} hrefLang={otherLang === 'en' ? 'en' : 'zh-CN'}>{t.other}</Link>
          <a className="gh" href={REPO} target="_blank" rel="noopener noreferrer">GitHub</a>
          <Link className="dl" href={`${address(lang, 'index')}#download`}>{t.download}</Link>
        </div>
      </header>
      {children}
      <footer className="foot">
        <div className="foot-map">
          <div className="foot-brand">
            <Link className="brand" href={address(lang, 'index')}>
              <img src={`${BASE}/favicon.svg`} alt="" width={28} height={28} /><span>{t.site}</span>
            </Link>
            <p>{t.tagline}</p>
          </div>
          {(['install', 'use', 'help', 'legal'] as Group[]).map(g => (
            <nav key={g} aria-label={t.groups[g]}>
              <h2>{t.groups[g]}</h2>
              {list.filter(p => p.group === g).map(p => <Link key={p.slug} href={p.href}>{p.name}</Link>)}
            </nav>
          ))}
        </div>
        <div className="foot-end">
          <p>{t.foot}</p>
          <p><a href={REPO} target="_blank" rel="noopener noreferrer">{t.source}</a> · Apache 2.0</p>
        </div>
      </footer>
    </div>
  );
}

/** A page of the site: a band with its group, icon, title and first lines, then its words in a
 * wide column, then the page that comes next. */
export function Doc({ lang, slug }: { lang: Lang; slug: string }) {
  const t = T[lang];
  const list = navPages(lang);
  const me = list.find(p => p.slug === slug)!;
  const next = list[list.findIndex(p => p.slug === slug) + 1];
  // the band takes the # title and the paragraph under it; the page keeps the rest
  const page = parts(lang, slug);
  // where the page sits, for a search result's trail (D222)
  const trail = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: t.site, item: `${SITE}${address(lang, 'index')}` },
      { '@type': 'ListItem', position: 2, name: page.title, item: `${SITE}${address(lang, slug)}` },
    ],
  };
  return (
    <Frame lang={lang} slug={slug}>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: ld(trail) }} />
      <header className="hero-band">
        <div className="hb-in">
          <span className="doc-ic"><PageIcon slug={slug} on /></span>
          <p className="hb-eyebrow">{t.groups[me.group]}</p>
          <h1>{page.title}</h1>
          <div className="hb-lede"><Markdown text={page.lede} lang={lang} /></div>
        </div>
      </header>
      <main className={`doc page${pages().find(p => p.slug === slug)?.source ? ' legal' : ''}`}>
        <Words text={page.body} lang={lang} slug={slug} />
        {next ? (
          <Link className="next" href={next.href}>
            <span className="nav-ic"><Icon name={next.icon} /></span>
            <span><small>{t.next}</small><b>{next.name}</b><em>{next.about}</em></span>
            <span className="next-go" aria-hidden="true">›</span>
          </Link>
        ) : null}
      </main>
    </Frame>
  );
}

/** The install pages' steps (D219): the package guides' own pictures, on the page. */
const STEPS: Record<string, Part[]> = {
  install: [{ kind: 'full' }],
  server: [
    { kind: 'server', only: [1, 2, 3, 4, 5], yaml: 2, title: { zh: '一、服务器（NAS 上）', en: '1. The server (on the NAS)' } },
    { kind: 'scanner', title: { zh: '二、扫描端（玩游戏的电脑上）', en: '2. The scanner (on the PC with the game)' } },
  ],
  // the Mac's own pictures (D228: "for mac version guideline you didnt include like the visual there")
  mac: [
    { kind: 'mac-full', title: { zh: 'mac-full：一台 Mac 全部搞定', en: 'mac-full: everything on one Mac' } },
    { kind: 'mac-scanner', title: { zh: 'mac-scanner：Mac 扫描，发给服务器', en: 'mac-scanner: the Mac scans, the server keeps it' } },
  ],
};

/** A troubleshooting answer: `{{guide:<kind>:<step>}}` on its own line stands for that step's
 * drawings in the guide, so someone who never opens the guide still sees them (D256). */
function Answer({ text, lang }: { text: string; lang: Lang }) {
  return (
    <>
      {text.split(/^(\{\{guide:[a-z-]+:\d+\}\})$/m).map((part, i) => {
        const [, kind, n] = /^\{\{guide:([a-z-]+):(\d+)\}\}$/.exec(part) ?? [];
        return kind
          ? <div key={i} className="gpic" dangerouslySetInnerHTML={{
              __html: guideSteps(kind, lang).find(s => s.n === Number(n))?.picture ?? '' }} />
          : <Markdown key={i} text={part} lang={lang} />;
      })}
    </>
  );
}

/** A page's words. An install page has its steps where `{{steps}}` stands; troubleshooting is a
 * list of questions, each folded until it is opened (D219). */
function Words({ text, lang, slug }: { text: string; lang: Lang; slug: string }) {
  if (STEPS[slug]) {
    const [before, after = ''] = text.split(/^\{\{steps\}\}$/m);
    return (
      <>
        <Markdown text={before} lang={lang} />
        <GuideSteps lang={lang} parts={STEPS[slug]} />
        <Markdown text={after} lang={lang} />
      </>
    );
  }
  if (slug === 'versions') {
    const [before, after = ''] = text.split(/^\{\{releases\}\}$/m);
    return (
      <>
        <Markdown text={before} lang={lang} />
        <Releases lang={lang} />
        <Markdown text={after} lang={lang} />
      </>
    );
  }
  if (slug === 'troubleshooting') {
    // ## groups the questions; each ### is one question, its answer folded under it
    const [intro, ...groups] = text.split(/^## /m);
    return (
      <>
        <Markdown text={intro} lang={lang} />
        {groups.map(group => {
          const [head, ...questions] = group.split(/^### /m);
          const [name, ...rest] = head.split('\n');
          return (
            <section key={name} className="faq">
              <h2>{name}</h2>
              <Markdown text={rest.join('\n')} lang={lang} />
              {questions.map(q => {
                const [question, ...answer] = q.split('\n');
                return (
                  <details key={question} className="q">
                    <summary>{question}</summary>
                    <Answer text={answer.join('\n')} lang={lang} />
                  </details>
                );
              })}
            </section>
          );
        })}
      </>
    );
  }
  if (/^\{\{text:/m.test(text)) {
    // the licence and its notice, as plain text, the way every package carries them (D223)
    return (
      <>
        {text.split(/^(\{\{text:[^}]+\}\})$/m).map((part, i) => {
          const file = /^\{\{text:([^}]+)\}\}$/.exec(part)?.[1];
          return file
            ? <section key={i} className="legal-file"><h2>{file}</h2><pre className="legal-text">{rootText(file)}</pre></section>
            : <Markdown key={i} text={part} lang={lang} />;
        })}
      </>
    );
  }
  return <Markdown text={text} lang={lang} />;
}

/** Every release, each side's changes or 没有改动 (D227): the list the app shows only the newest
 * and in-use part of, whole. */
function Releases({ lang }: { lang: Lang }) {
  const said = (c: { zh: string; en: string }) => (lang === 'en' ? c.en : c.zh);
  const sides = [['scanner', lang === 'en' ? 'Scanner' : '扫描端'], ['home', lang === 'en' ? 'Server' : '服务器']] as const;
  return (
    <ol className="releases">
      {releases().map((r, i) => (
        <li key={r.version} id={`v${r.version}`}>
          <div className="rel-h"><b>v{r.version}</b><small>{r.date}</small>
            {i === 0 ? <span className="rel-tag">{lang === 'en' ? 'newest' : '最新'}</span> : null}</div>
          <div className="sides">
            {sides.map(([k, name]) => (
              <div key={k} className={`side by-${k}${r[k].length ? '' : ' none'}`}>
                <span className="side-n">{name}</span>
                {r[k].length
                  ? <ul>{r[k].map((c, j) => <li key={j}>{said(c)}</li>)}</ul>
                  : <p className="nothing">{lang === 'en' ? 'No changes' : '没有改动'}</p>}
              </div>
            ))}
          </div>
        </li>
      ))}
    </ol>
  );
}

/** Where a page that is no more has gone (D228): the Mac guides' pages are pictures on the Mac
 * page. The old address forwards there, and tells search engines the new one is the page. */
export function movedMetadata(lang: Lang, to: string): Metadata {
  return { title: T[lang].site, robots: { index: false, follow: true },
           alternates: { canonical: `${SITE}${address(lang, to)}` } };
}

export function Moved({ lang, to }: { lang: Lang; to: string }) {
  const href = address(lang, to);
  return (
    <Frame lang={lang}>
      <meta httpEquiv="refresh" content={`0; url=${BASE}${href}`} />
      <main className="lost">
        <h1>{lang === 'en' ? 'This page has moved' : '这一页搬家了'}</h1>
        <div className="lost-a"><Link className="btn gold" href={href}>{lang === 'en' ? 'Go there ›' : '去新地址 ›'}</Link></div>
      </main>
    </Frame>
  );
}
