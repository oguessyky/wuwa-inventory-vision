'use client';

import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { GuideStep, Lang } from '@/lib/content';

// The download button's icon (D214), traced from Gemini's frames in the app's icon family: a tray,
// an arrow, and a check, drawn in one frame so each can move on its own. On hover the arrow drops
// into the tray and back; on a click it goes in, the tray gives, and a check takes its place.
const ARROW = 'M10.6 3.0L13.4 3.1L13.4 10.9L13.5 11.1L13.7 11.2L16.2 11.2L16.0 11.5L16.0 11.6L14.8 12.7L14.8 12.8L13.6 14.0L13.6 14.2L12.2 15.6L12.0 15.8L11.2 15.0L11.2 14.8L7.8 11.2L10.3 11.2L10.4 11.2L10.6 11.0ZM10.1 2.0L9.9 2.0L9.6 2.3L9.6 10.2L6.5 10.3L6.4 10.3L6.2 10.5L6.2 11.0L6.3 11.2L7.3 12.2L7.4 12.3L8.4 13.4L8.4 13.5L9.6 14.7L9.7 14.8L10.7 15.9L10.7 16.0L11.7 17.0L12.2 17.0L12.4 17.0L12.8 16.5L12.8 16.4L15.1 14.0L15.1 13.9L16.2 12.9L16.2 12.8L17.4 11.5L17.5 11.4L17.8 11.1L17.9 10.9L17.9 10.6L17.6 10.3L17.5 10.3L14.4 10.2L14.4 2.3L14.2 2.1L13.9 2.0Z';
const TRAY = 'M3.2 15.8L4.4 15.8L4.4 19.0L4.6 19.3L4.9 19.4L19.1 19.4L19.4 19.3L19.6 19.1L19.6 15.8L20.8 15.8L20.9 20.7L3.2 20.7ZM2.2 15.2L2.2 21.2L2.3 21.4L2.5 21.6L21.5 21.6L21.8 21.4L21.9 21.2L21.9 15.2L21.8 15.0L21.6 14.8L19.0 14.8L18.7 15.0L18.5 15.2L18.5 18.4L5.5 18.4L5.4 15.1L5.2 14.8L2.6 14.8L2.5 14.8Z';
const CHECK = 'M16.7 7.5L16.4 7.9L15.3 8.9L15.3 9.1L13.4 11.1L13.3 11.2L12.6 12.0L12.5 12.1L10.7 14.0L7.6 10.9L7.6 10.8L8.2 10.2L10.4 12.4L10.9 12.4L11.8 11.5L11.9 11.4L12.6 10.6L12.7 10.5L13.6 9.5L13.7 9.4L14.7 8.4L14.7 8.2L16.0 6.9ZM16.3 5.5L15.7 5.5L10.6 11.1L8.6 8.9L8.2 8.8L7.9 8.9L6.3 10.5L6.3 11.1L10.4 15.3L10.7 15.4L11.0 15.3L11.9 14.4L12.0 14.3L12.9 13.4L13.0 13.2L13.9 12.3L13.9 12.2L14.8 11.3L14.8 11.2L15.8 10.2L15.8 10.1L17.8 8.0L18.0 7.8L18.0 7.2Z';

export function DownloadIcon() {
  return (
    <svg className="dli" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path className="dli-arrow" fillRule="evenodd" d={ARROW} />
      <path className="dli-check" fillRule="evenodd" d={CHECK} />
      <path className="dli-tray" fillRule="evenodd" d={TRAY} />
    </svg>
  );
}

/** What comes after a download (D267): the package's zip, its guide, and the guide's steps from
 * the zip to the first double-click. */
export interface After { lang: Lang; file: string; guide: string; steps: GuideStep[] }

/** A download link whose icon plays when pressed: the browser's download starts as the arrow lands.
 * Given `after`, the same click opens the steps that get from the zip to START-HERE (D267). */
export function DownloadLink({ href, className, children, download = true, after }: {
  href: string; className?: string; children: ReactNode; download?: boolean; after?: After;
}) {
  const [done, setDone] = useState(false);
  const [open, setOpen] = useState(false);
  return (
    <>
      <a className={`dlb${done ? ' done' : ''}${className ? ' ' + className : ''}`} href={href} download={download || undefined}
         onClick={() => { setDone(true); setTimeout(() => setDone(false), 2200); if (after?.steps.length) setOpen(true); }}>
        <DownloadIcon />{children}
      </a>
      {after?.steps.length ? <AfterDownload after={after} open={open} onClose={() => setOpen(false)} /> : null}
    </>
  );
}

const AFTER = {
  zh: {
    started: '下载开始了', next: (n: number) => `下载好以后，照这 ${n} 步打开它`,
    step: (i: number, n: number) => `第 ${i} / ${n} 步`, back: '上一步', on: '下一步', got: '知道了',
    guide: '整份图文指南', here: '解压后的文件夹里有 START-HERE.html，就是这份指南。', close: '关闭',
  },
  en: {
    started: 'Your download has started', next: (n: number) => `Once it is down, these ${n} steps open it`,
    step: (i: number, n: number) => `Step ${i} of ${n}`, back: 'Back', on: 'Next', got: 'Got it',
    guide: 'The whole guide', here: 'The unzipped folder has START-HERE.html: this same guide.', close: 'Close',
  },
};

/**
 * The pop-up after a download (D267). The user, 2026-11-11: "after click download it should
 * have pop up or redirect the step to get to the start here there, else people are easy to
 * always require unzip at least two times." The zip holds one folder, so Extract All leaves a
 * folder in a folder: these are the guide's own steps and drawings, one at a time, from the
 * zip to the first double-click, and the whole guide a click away.
 */
function AfterDownload({ after, open, onClose }: { after: After; open: boolean; onClose: () => void }) {
  const w = AFTER[after.lang];
  const ref = useRef<HTMLDialogElement>(null);
  const [at, setAt] = useState(0);
  useEffect(() => {
    const d = ref.current;
    if (open && d && !d.open) { setAt(0); d.showModal(); }
  }, [open]);
  const close = () => ref.current?.close();
  const steps = after.steps;
  const s = steps[at];
  const last = at === steps.length - 1;
  return (
    <dialog ref={ref} className="after" aria-labelledby={`after-${after.file}`} onClose={onClose}
            onClick={e => { if (e.target === ref.current) close(); }}>
      <div className="after-in">
        <header className="after-h">
          <span className="after-ok" aria-hidden="true"><DownloadIcon /></span>
          <div>
            <h2 id={`after-${after.file}`}>{w.started}</h2>
            <p><code>{after.file}</code><span>{w.next(steps.length)}</span></p>
          </div>
          <button type="button" className="after-x" onClick={close} aria-label={w.close}>×</button>
        </header>
        <ol className="after-dots">
          {steps.map((st, i) => (
            <li key={st.n}>
              <button type="button" aria-current={i === at ? 'step' : undefined} className={i < at ? 'past' : ''} onClick={() => setAt(i)}>
                <span>{i + 1}</span><b dangerouslySetInnerHTML={{ __html: st.title }} />
              </button>
            </li>
          ))}
        </ol>
        <section className="after-step" data-step={s.n}>
          <p className="after-n">{w.step(at + 1, steps.length)}</p>
          <h3 dangerouslySetInnerHTML={{ __html: s.title }} />
          {s.text.map((p, i) => <p key={i} dangerouslySetInnerHTML={{ __html: p }} />)}
          <div className="gpic" dangerouslySetInnerHTML={{ __html: s.picture }} />
        </section>
        <footer className="after-f">
          <p>{w.here} <a href={after.guide}>{w.guide} ›</a></p>
          <div>
            {at ? <button type="button" className="btn line" onClick={() => setAt(at - 1)}>{w.back}</button> : null}
            {last ? <button type="button" className="btn gold" onClick={close}>{w.got}</button>
              : <button type="button" className="btn gold" onClick={() => setAt(at + 1)}>{w.on} ›</button>}
          </div>
        </footer>
      </div>
    </dialog>
  );
}
