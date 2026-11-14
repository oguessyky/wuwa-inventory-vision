'use client';

import { useEffect, useState } from 'react';

/**
 * A guide's sections beside its words (D294), on a wide screen: each a link to its part, the one
 * being read marked as you scroll -- the half of the page that was empty, put to use.
 */
export function Toc({ items, title }: { items: { id: string; text: string }[]; title: string }) {
  const [here, setHere] = useState(items[0]?.id ?? '');
  useEffect(() => {
    const seen = new Map<string, boolean>();
    // each part's whole panel, not its heading alone (D301): with its pictures a part is taller
    // than the screen, and in the middle of one no heading is in sight
    const part = new Map<Element, string>();
    const watch = new IntersectionObserver(entries => {
      for (const e of entries) seen.set(part.get(e.target) ?? '', e.isIntersecting);
      const first = items.find(it => seen.get(it.id));
      if (first) setHere(first.id);
    }, { rootMargin: '-80px 0px -55% 0px' });
    for (const it of items) {
      const heading = document.getElementById(it.id);
      const el = heading?.closest('section') ?? heading;
      if (el) { part.set(el, it.id); watch.observe(el); }
    }
    return () => watch.disconnect();
  }, [items]);
  return (
    <aside className="toc" aria-label={title}>
      <p className="toc-h">{title}</p>
      <ol>
        {items.map((it, i) => (
          <li key={it.id}>
            <a href={`#${it.id}`} aria-current={here === it.id ? 'location' : undefined}>
              <span className="toc-n">{i + 1}</span>{it.text}</a>
          </li>
        ))}
      </ol>
    </aside>
  );
}
