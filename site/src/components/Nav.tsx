'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useRef, useState, type PointerEvent } from 'react';
import type { Group, Lang } from '@/lib/content';
import { Icon } from './Icons';

// The bar across the top (D221). The user, 2026-10-27, of the menu down the side of every page:
// "I dont want something like this, as current you can made it like an acture product/system
// page". The pages in three groups -- install, use, help -- each a menu of its pages with a line
// that says what each is for. On a phone, one button opens them all.

export interface NavPage { slug: string; name: string; about: string; href: string; icon: string; group: Group }

/** the bar's groups; the legal pages are in the foot (D223) */
type Bar = Extract<Group, 'install' | 'use' | 'help'>;
const GROUPS: Bar[] = ['install', 'use', 'help'];
const W = {
  zh: { install: '安装', use: '使用', help: '帮助', menu: '菜单', nav: '网站导航', here: '当前位置' },
  en: { install: 'Install', use: 'Use', help: 'Help', menu: 'Menu', nav: 'Site', here: 'You are here' },
};
/** What each group is for, at the head of its menu (D295). */
const ABOUT: Record<Lang, Record<Bar, string>> = {
  zh: {
    install: '在你的电脑、Mac 或 NAS 上装好它：选一种装法，跟着图一步步来。',
    use: '装好之后：扫描背包，看每一页帮你算什么，算伤害和配队，以及更新。',
    help: '遇到问题先看这里；以及它只看屏幕、资料留在你这里的说明。',
  },
  en: {
    install: 'Install it on your PC, a Mac or a NAS: pick a setup and follow the pictures step by step.',
    use: 'Once it is set up: scanning, what each page works out, the calculator and teams, updating.',
    help: 'Start here when something is in trouble; and how it only looks at the screen, your data staying yours.',
  },
};

function Item({ p, on }: { p: NavPage; on: boolean }) {
  return (
    <Link href={p.href} className={on ? 'on' : ''} aria-current={on ? 'page' : undefined}>
      <span className="nav-ic"><Icon name={`${p.icon}${on ? '-on' : ''}`} /></span>
      <span className="nav-t"><b>{p.name}</b><small>{p.about}</small></span>
    </Link>
  );
}

export function Nav({ lang, slug, pages }: { lang: Lang; slug?: string; pages: NavPage[] }) {
  const w = W[lang];
  const current = pages.find(p => p.slug === slug && GROUPS.includes(p.group as Bar));
  const [open, setOpen] = useState<Bar | null>(null);
  const [sheet, setSheet] = useState(false);
  const path = usePathname();
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => { setOpen(null); setSheet(false); }, [path]);
  useEffect(() => {
    const away = (e: Event) => { if (root.current && !root.current.contains(e.target as Node)) { setOpen(null); setSheet(false); } };
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') { setOpen(null); setSheet(false); } };
    document.addEventListener('pointerdown', away);
    document.addEventListener('keydown', esc);
    return () => { document.removeEventListener('pointerdown', away); document.removeEventListener('keydown', esc); };
  }, []);
  // a mouse opens a group by resting on it; a finger by tapping it (a tap is not a hover)
  const hoverAt = useRef(0);
  const hover = (g: Bar | null) => (e: PointerEvent) => {
    if (e.pointerType === 'mouse') { setOpen(g); hoverAt.current = Date.now(); }
  };
  // a click right after the pointer opened it keeps it open, rather than shutting it at once
  const press = (g: Bar) => setOpen(o => (o === g && Date.now() - hoverAt.current < 500 ? g : o === g ? null : g));
  return (
    <div className="nav-root" ref={root}>
      <nav className="nav" aria-label={w.nav}>
        {GROUPS.map(g => {
          const items = pages.filter(p => p.group === g);
          const here = items.some(p => p.slug === slug);
          return (
            <div key={g} className={`nav-g${open === g ? ' open' : ''}${here ? ' here' : ''}`}
                 onPointerEnter={hover(g)} onPointerLeave={hover(null)}>
              <button type="button" aria-expanded={open === g} aria-controls={`nav-${g}`}
                      onClick={() => press(g)}>
                {w[g]}<svg className="chev" viewBox="0 0 12 12" aria-hidden="true"><path d="M3 4.5l3 3 3-3" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
              </button>
              {/* wide, with what the group is for at its head; four pages or more in two columns (D295) */}
              <div className={`nav-panel${items.length >= 4 ? ' cols' : ''}`} id={`nav-${g}`}>
                <p className="nav-head"><b>{w[g]}</b>{ABOUT[lang][g]}</p>
                <div className="nav-items">{items.map(p => <Item key={p.slug} p={p} on={p.slug === slug} />)}</div>
              </div>
            </div>
          );
        })}
        {/* where you are: the group, then the page (D295) */}
        {current ? (
          <span className="trail" aria-label={w.here}>
            <span>{w[current.group as Bar] ?? ''}</span><i aria-hidden="true">›</i><b>{current.name}</b>
          </span>
        ) : null}
      </nav>
      <button type="button" className="burger" aria-expanded={sheet} aria-controls="nav-sheet" aria-label={w.menu}
              onClick={() => setSheet(!sheet)}>
        <svg viewBox="0 0 24 24" aria-hidden="true">
          {sheet
            ? <path d="M6 6l12 12M18 6L6 18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            : <path d="M4 7h16M4 12h16M4 17h16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />}
        </svg>
      </button>
      <div className={`sheet${sheet ? ' open' : ''}`} id="nav-sheet">
        {GROUPS.map(g => (
          <section key={g}>
            <h2>{w[g]}</h2>
            {pages.filter(p => p.group === g).map(p => <Item key={p.slug} p={p} on={p.slug === slug} />)}
          </section>
        ))}
      </div>
    </div>
  );
}
