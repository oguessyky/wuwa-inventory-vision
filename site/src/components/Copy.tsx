'use client';

import { useState } from 'react';
import type { Lang } from '@/lib/content';

/** A command, copied in one click: what a guide asks you to type is never retyped by hand. An
 * icon in the block's corner (D221): two sheets, a tick once it is copied. */
export function Copy({ text, lang }: { text: string; lang: Lang }) {
  const [done, setDone] = useState(false);
  const label = done ? (lang === 'en' ? 'Copied' : '已复制') : (lang === 'en' ? 'Copy' : '复制');
  return (
    <button type="button" className={`copy${done ? ' done' : ''}`} aria-label={label} title={label} onClick={async () => {
      try { await navigator.clipboard.writeText(text); setDone(true); setTimeout(() => setDone(false), 1600); }
      catch { /* no clipboard here: the text can still be selected */ }
    }}>
      {done
        ? <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
        : <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="8.5" y="8.5" width="11" height="11" rx="2.2" fill="none" stroke="currentColor" strokeWidth="1.6" /><path d="M15.5 5.6V5.2a1.7 1.7 0 0 0-1.7-1.7H6.2a1.7 1.7 0 0 0-1.7 1.7v7.6a1.7 1.7 0 0 0 1.7 1.7h.4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>}
      <span className="copy-t" aria-hidden="true">{done ? label : ''}</span>
    </button>
  );
}
