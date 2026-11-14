'use client';

import { useEffect, useState } from 'react';

/**
 * A guide's picture (D294): shown in the page, and at its full size over the page on a click --
 * a screenshot is often more than a column shows. Escape, a click or the close button puts it away.
 */
export function Zoom({ src, alt, narrow, lang }: { src: string; alt: string; narrow: boolean; lang: 'zh' | 'en' }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!open) return;
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('keydown', key);
    return () => document.removeEventListener('keydown', key);
  }, [open]);
  const label = lang === 'en' ? 'Open at full size' : '查看大图';
  return (
    <>
      <button type="button" className={`zoom${narrow ? ' narrow' : ''}`} onClick={() => setOpen(true)} aria-label={`${label}: ${alt}`}>
        <img src={src} alt={alt} loading="lazy" />
      </button>
      {open ? (
        <div className="zoomed" role="dialog" aria-modal="true" aria-label={alt} onClick={() => setOpen(false)}>
          <img src={src} alt={alt} />
          <button type="button" className="zoom-x" aria-label={lang === 'en' ? 'Close' : '关闭'} onClick={() => setOpen(false)}>✕</button>
        </div>
      ) : null}
    </>
  );
}
