import { Fragment, type ReactNode } from 'react';
import type { Lang } from '@/lib/content';
import { Copy } from './Copy';

// A block of code (D221). The user, 2026-10-27, with a compose file coloured the way a code host
// shows it: "for like the docker one you can made it like this mah". YAML gets its keys, values
// and comments each a colour; a command is shown as it is. The whole of it is shown -- no box
// that scrolls inside the page -- and Copy is an icon in its corner.

/** One line of YAML, as spans: `tok-k` a key, `tok-v` its value, `tok-c` a comment, `tok-p` the
 * punctuation between. Enough for a compose file; anything it does not know stays plain. */
function yamlLine(line: string, k: number): ReactNode {
  const comment = /^(\s*)(#.*)$/.exec(line);
  if (comment) return <span key={k}>{comment[1]}<span className="tok-c">{comment[2]}</span></span>;
  const pair = /^(\s*)(- )?([\w.-]+)(:)(\s*)(.*)$/.exec(line);
  if (pair) {
    return (
      <span key={k}>{pair[1]}{pair[2] ? <span className="tok-p">{pair[2]}</span> : null}
        <span className="tok-k">{pair[3]}</span><span className="tok-p">{pair[4]}</span>{pair[5]}
        {pair[6] ? <span className="tok-v">{pair[6]}</span> : null}</span>
    );
  }
  const item = /^(\s*)(- )(.*)$/.exec(line);
  if (item) return <span key={k}>{item[1]}<span className="tok-p">{item[2]}</span><span className="tok-v">{item[3]}</span></span>;
  return <span key={k}>{line}</span>;
}

export function Code({ text, lang, site }: { text: string; lang?: string; site: Lang }) {
  const lines = text.replace(/\s+$/, '').split('\n');
  return (
    <div className={`code${lang ? ` code-${lang}` : ''}`}>
      <pre><code>{lang === 'yaml'
        ? lines.map((line, k) => <Fragment key={k}>{yamlLine(line, k)}{k < lines.length - 1 ? '\n' : null}</Fragment>)
        : lines.join('\n')}</code></pre>
      <Copy text={text} lang={site} />
    </div>
  );
}
