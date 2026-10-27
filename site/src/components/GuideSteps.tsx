import { compose, downloads, guideSteps, type Lang } from '@/lib/content';
import { Code } from './Code';
import { DownloadLink } from './Download';
import { Icon } from './Icons';

// The install pages' steps (D219): the package's own guide -- the one its zip carries as
// START-HERE -- shown on the page as cards, a drawing each, instead of a link to a second guide.
// The drawings and the few words are the project's own (tools/make_guides.py), so they go in as
// they are written there.

export interface Part {
  kind: 'full' | 'scanner' | 'home';
  /** a heading above this part's steps, when a page has more than one part */
  title?: { zh: string; en: string };
  /** the steps to show, by number; the rest are left to the full guide */
  only?: number[];
  /** the step that pastes the home's compose file: the file itself goes under it, to copy */
  yaml?: number;
}

const BASE = process.env.NEXT_PUBLIC_BASE_PATH || '';
const T = {
  zh: { download: '下载', guide: '整份图文指南（可打印）', step: '第', of: '步',
        yaml: '要粘贴的 Compose 配置（复制后只换掉 tskey-auth-PUT-YOURS-HERE）' },
  en: { download: 'Download', guide: 'The whole guide (to print)', step: 'Step', of: '',
        yaml: 'The Compose configuration to paste (copy it, then change only tskey-auth-PUT-YOURS-HERE)' },
};

export function GuideSteps({ lang, parts }: { lang: Lang; parts: Part[] }) {
  const t = T[lang];
  const zips = downloads();
  return (
    <div className="gsteps">
      {parts.map(part => {
        const steps = guideSteps(part.kind, lang).filter(s => !part.only || part.only.includes(s.n));
        return (
          <section key={part.kind} className="gpart">
            <div className="gpart-h">
              {part.title ? <h2>{part.title[lang]}</h2> : null}
              <div className="gpart-a">
                <DownloadLink className="btn gold" href={zips[part.kind].url}>
                  <span className="nw">{t.download}</span> <code>{zips[part.kind].file}</code>
                </DownloadLink>
                <a className="gpart-g" href={`${BASE}/guides/${part.kind}.html`}><Icon name="planner" />{t.guide}</a>
              </div>
            </div>
            <ol className="gcards">
              {steps.map(s => (
                <li key={s.n} className="gcard">
                  <div className="gcard-t">
                    <span className="gnum" aria-label={`${t.step} ${s.n} ${t.of}`}>{s.n}</span>
                    <div>
                      <h3 dangerouslySetInnerHTML={{ __html: s.title }} />
                      {s.text.map((p, i) => <p key={i} dangerouslySetInnerHTML={{ __html: p }} />)}
                      {s.tips.map((p, i) => <p key={`t${i}`} className="gtip" dangerouslySetInnerHTML={{ __html: p }} />)}
                    </div>
                  </div>
                  <div className="gpic" dangerouslySetInnerHTML={{ __html: s.picture }} />
                  {part.yaml === s.n ? (
                    <div className="yaml">
                      <p className="yaml-h"><span className="yaml-f">docker-compose.yaml</span><span>{t.yaml}</span></p>
                      <Code lang="yaml" text={compose()} site={lang} />
                    </div>
                  ) : null}
                </li>
              ))}
            </ol>
          </section>
        );
      })}
    </div>
  );
}
