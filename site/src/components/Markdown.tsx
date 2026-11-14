import Link from 'next/link';
import { Fragment, type ReactNode } from 'react';
import type { Lang } from '@/lib/content';
import { pngSize } from '@/lib/png';
import { Code } from './Code';
import { Zoom } from './Zoom';

// Just enough Markdown for the site's own pages (D210), as the app's (D162) with what a guide
// needs besides: links, pictures, numbered steps, blocks of commands and tables (a package's guide, D214). Built as React nodes,
// never as HTML, so nothing in a file can put markup into the page.

const BASE = process.env.NEXT_PUBLIC_BASE_PATH || '';

/** A screenshot as the page shows it: the WebP made beside it while the site is built (D230). The
 * words name the PNG, which docs/screens holds and the README shows. */
const webp = (src: string) => (src.startsWith('screens/') ? src.replace(/\.(png|jpe?g)$/i, '.webp') : src);

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
  const re = /\*\*(.+?)\*\*|`([^`]+)`|\[([^\]]+)\]\(([^)]+)\)|<(https?:\/\/[^>]+)>|\*([^*\s][^*]*?)\*/g;
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
    } else if (m[5] != null) out.push(<a key={k} href={m[5]} target="_blank" rel="noopener noreferrer">{m[5]}</a>);
    else out.push(<em key={k}>{inline(m[6], k, lang)}</em>);           // *a title* (D223)
    at = m.index + m[0].length;
  }
  if (at < text.length) out.push(text.slice(at));
  return out;
}

/** An id for a heading, so a section can be linked to. */
export const anchor = (text: string) =>
  text.replace(/[*`]/g, '').trim().toLowerCase().replace(/[^\p{L}\p{N}]+/gu, '-').replace(/^-|-$/g, '');

/** A screenshot narrower than this (in its own pixels) sits beside its words (D294): the 计算
 * guide's parts, at twice the pixels, are; a whole page, at 1400, is not. */
const NARROW = 1000;

/** The blocks of a page: headings, paragraphs, lists, pictures and command blocks. With
 * `sections` (a guide's body, D294), each ## and what follows it is a panel of its own; one
 * whose only picture is narrow has it beside its words. */
export function Markdown({ text, lang, sections = false }: { text: string; lang: Lang; sections?: boolean }) {
  const blocks: ReactNode[] = [];
  // the sections, as indexes into `blocks`: where each starts, and its pictures
  const parts: { at: number; id: string; narrow: number; wide: number }[] = [];
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
      const fence = line.slice(3).trim();             // ```yaml: coloured as YAML (D221)
      const code: string[] = [];
      for (i++; i < lines.length && !lines[i].startsWith('```'); i++) code.push(lines[i]);
      blocks.push(<Code key={`c${blocks.length}`} text={code.join('\n')} lang={fence || undefined} site={lang} />);
      continue;
    }
    if (line.startsWith('|')) {                       // a table: | a | b |, then |---|---|
      flush();
      const rows: string[][] = [];
      for (; i < lines.length && lines[i].trimEnd().startsWith('|'); i++)
        rows.push(lines[i].trim().replace(/^\||\|$/g, '').split('|').map(cell => cell.trim()));
      i--;
      const [head, , ...body] = rows;
      const k = `t${blocks.length}`;
      blocks.push(<div className="tbl" key={k}><table>
        {head.some(Boolean) ? <thead><tr>{head.map((c, j) => <th key={j}>{inline(c, `${k}h${j}`, lang)}</th>)}</tr></thead> : null}
        <tbody>{body.map((row, r) => <tr key={r}>{row.map((c, j) =>
          <td key={j}>{inline(c, `${k}-${r}-${j}`, lang)}</td>)}</tr>)}</tbody></table></div>);
      continue;
    }
    if (line.startsWith('>')) {                       // > a line quoted, as the notices have (D223)
      flush();
      const quoted: string[] = [];
      for (; i < lines.length && lines[i].startsWith('>'); i++) quoted.push(lines[i].replace(/^>\s?/, ''));
      i--;
      const k = `q${blocks.length}`;
      blocks.push(<blockquote key={k}><p>{inline(quoted.join(' '), k, lang)}</p></blockquote>);
      continue;
    }
    if (!line.trim()) { flush(); continue; }
    const picture = /^!\[([^\]]*)\]\(([^)]+)\)$/.exec(line.trim());
    if (picture) {
      flush();
      const size = pngSize(picture[2]);
      const narrow = !!size && size.width < NARROW;
      const part = parts[parts.length - 1];
      if (part) part[narrow ? 'narrow' : 'wide'] += 1;
      // a phone stood up (D301): taller than half again its width, shown about a phone's size
      const tall = !!size && size.height > size.width * 1.5;
      blocks.push(<figure key={`f${blocks.length}`} className={[narrow && 'narrow', tall && 'tall'].filter(Boolean).join(' ') || undefined}>
        <Zoom src={`${BASE}/${webp(picture[2])}`} alt={picture[1]} narrow={narrow} lang={lang} />
        {picture[1] ? <figcaption>{picture[1]}</figcaption> : null}</figure>);
      continue;
    }
    const heading = /^(#{1,3}) (.*)$/.exec(line);
    if (heading) {
      flush();
      const k = `h${blocks.length}`;
      const id = anchor(heading[2]);
      if (heading[1] === '#') blocks.push(<h1 key={k}>{inline(heading[2], k, lang)}</h1>);
      else if (heading[1] === '##') {
        if (sections) parts.push({ at: blocks.length, id, narrow: 0, wide: 0 });
        blocks.push(<h2 key={k} id={id}>{inline(heading[2], k, lang)}</h2>);
      }
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
  if (!sections || !parts.length) return <Fragment>{blocks}</Fragment>;
  // what comes before the first ## stays as it is; each ## is a panel, numbered by the page
  return (
    <Fragment>
      {blocks.slice(0, parts[0].at)}
      {parts.map((part, i) => {
        const end = parts[i + 1]?.at ?? blocks.length;
        const side = part.narrow === 1 && part.wide === 0;
        return (
          <section key={part.id} className={`sec${side ? ' side' : ''}`} data-n={i + 1} aria-labelledby={part.id}>
            {blocks.slice(part.at, end)}
          </section>
        );
      })}
    </Fragment>
  );
}
