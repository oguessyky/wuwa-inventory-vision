import Link from 'next/link';
import { Fragment, type ReactNode } from 'react';
import type { Lang } from '@/lib/content';
import { Copy } from './Copy';

// Just enough Markdown for the site's own pages (D210), as the app's (D162) with what a guide
// needs besides: links, pictures, numbered steps and blocks of commands. Built as React nodes,
// never as HTML, so nothing in a file can put markup into the page.

const BASE = process.env.NEXT_PUBLIC_BASE_PATH || '';

/** An address in the words: '/install' is a page of the site, in the page's own language. */
function to(href: string, lang: Lang): string {
  if (!href.startsWith('/')) return href;
  const [path, hash] = href.split('#');
  const page = path === '/' ? '/' : `${path.replace(/\/$/, '')}/`;
  return `${lang === 'en' ? '/en' : ''}${page}${hash ? `#${hash}` : ''}`;
}

/** **bold**, `code`, [links](...) and <https://...> inside one line of text. */
function inline(text: string, key: string, lang: Lang): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /\*\*(.+?)\*\*|`([^`]+)`|\[([^\]]+)\]\(([^)]+)\)|<(https?:\/\/[^>]+)>/g;
  let at = 0;
  for (let m = re.exec(text); m; m = re.exec(text)) {
    if (m.index > at) out.push(text.slice(at, m.index));
    const k = `${key}-${m.index}`;
    if (m[1] != null) out.push(<b key={k}>{inline(m[1], k, lang)}</b>);
    else if (m[2] != null) out.push(<code key={k}>{m[2]}</code>);
    else if (m[3] != null) {
      const href = m[4];
      out.push(href.startsWith('/')
        ? <Link key={k} href={to(href, lang)}>{inline(m[3], k, lang)}</Link>
        : <a key={k} href={href} target="_blank" rel="noopener noreferrer">{inline(m[3], k, lang)}</a>);
    } else out.push(<a key={k} href={m[5]} target="_blank" rel="noopener noreferrer">{m[5]}</a>);
    at = m.index + m[0].length;
  }
  if (at < text.length) out.push(text.slice(at));
  return out;
}

/** An id for a heading, so a section can be linked to. */
export const anchor = (text: string) =>
  text.replace(/[*`]/g, '').trim().toLowerCase().replace(/[^\p{L}\p{N}]+/gu, '-').replace(/^-|-$/g, '');

/** The blocks of a page: headings, paragraphs, lists, pictures and command blocks. */
export function Markdown({ text, lang }: { text: string; lang: Lang }) {
  const blocks: ReactNode[] = [];
  const lines = text.replace(/\r\n/g, '\n').split('\n');
  let para: string[] = [];
  let list: string[] = [];
  let numbered = false;
  const flush = () => {
    const k = `b${blocks.length}`;
    if (para.length) blocks.push(<p key={k}>{inline(para.join(' '), k, lang)}</p>);
    else if (list.length) {
      const items = list.map((item, i) => <li key={i}>{inline(item, `${k}-${i}`, lang)}</li>);
      blocks.push(numbered ? <ol key={k}>{items}</ol> : <ul key={k}>{items}</ul>);
    }
    para = [];
    list = [];
  };
  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    const line = raw.trimEnd();
    if (line.startsWith('```')) {                     // a block of commands, to copy
      flush();
      const code: string[] = [];
      for (i++; i < lines.length && !lines[i].startsWith('```'); i++) code.push(lines[i]);
      const k = `c${blocks.length}`;
      blocks.push(<div className="cmd" key={k}><pre><code>{code.join('\n')}</code></pre><Copy text={code.join('\n')} lang={lang} /></div>);
      continue;
    }
    if (!line.trim()) { flush(); continue; }
    const picture = /^!\[([^\]]*)\]\(([^)]+)\)$/.exec(line.trim());
    if (picture) {
      flush();
      blocks.push(<figure key={`f${blocks.length}`}><img src={`${BASE}/${picture[2]}`} alt={picture[1]} loading="lazy" />
        {picture[1] ? <figcaption>{picture[1]}</figcaption> : null}</figure>);
      continue;
    }
    const heading = /^(#{1,3}) (.*)$/.exec(line);
    if (heading) {
      flush();
      const k = `h${blocks.length}`;
      const id = anchor(heading[2]);
      if (heading[1] === '#') blocks.push(<h1 key={k}>{inline(heading[2], k, lang)}</h1>);
      else if (heading[1] === '##') blocks.push(<h2 key={k} id={id}>{inline(heading[2], k, lang)}</h2>);
      else blocks.push(<h3 key={k} id={id}>{inline(heading[2], k, lang)}</h3>);
      continue;
    }
    const item = /^(- |\d+\. )(.*)$/.exec(line);
    if (item) {
      if (para.length || (list.length && numbered !== (item[1] !== '- '))) flush();
      numbered = item[1] !== '- ';
      list.push(item[2]);
    } else if (list.length && /^\s+\S/.test(raw)) {
      list[list.length - 1] += ' ' + line.trim();        // an item carried onto the next line
    } else {
      if (list.length) flush();
      para.push(line.trim());
    }
  }
  flush();
  return <Fragment>{blocks}</Fragment>;
}
