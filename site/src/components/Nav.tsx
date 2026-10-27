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
  zh: { install: '安装', use: '使用', help: '帮助', menu: '菜单', nav: '网站导航' },
  en: { install: 'Install', use: 'Use', help: 'Help', menu: 'Menu', nav: 'Site' },
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
              <div className="nav-panel" id={`nav-${g}`}>
                {items.map(p => <Item key={p.slug} p={p} on={p.slug === slug} />)}
              </div>
            </div>
          );
        })}
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
