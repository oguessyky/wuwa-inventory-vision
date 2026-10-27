'use client';

import { useState } from 'react';
import type { Lang } from '@/lib/content';

/** A command, copied in one click: what a guide asks you to type is never retyped by hand. */
export function Copy({ text, lang }: { text: string; lang: Lang }) {
  const [done, setDone] = useState(false);
  return (
    <button type="button" className="copy" onClick={async () => {
      try { await navigator.clipboard.writeText(text); setDone(true); setTimeout(() => setDone(false), 1600); }
      catch { /* no clipboard here: the text can still be selected */ }
    }}>{done ? (lang === 'en' ? 'Copied' : '已复制') : (lang === 'en' ? 'Copy' : '复制')}</button>
  );
}
