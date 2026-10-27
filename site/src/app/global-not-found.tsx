import Link from 'next/link';
import type { Metadata } from 'next';
import { Frame } from '@/components/Doc';
import { ROOT_METADATA, VIEWPORT } from '@/lib/seo';
import './site.css';

// The page GitHub Pages serves for an address that is not there (D222): in the site's own frame,
// in both languages, and kept out of search results. Each language is its own root (one layout
// each), so this page is a whole document of its own.
export const metadata: Metadata = {
  ...ROOT_METADATA,
  title: '找不到这一页 · Page not found',
  robots: null,                       // Next marks it noindex itself
};
export const viewport = VIEWPORT;

export default function NotFound() {
  return (
    <html lang="zh-CN">
      <body>
        <Frame lang="zh">
          <main className="lost">
            <p className="lost-n">404</p>
            <h1>找不到这一页</h1>
            <p lang="en">This page is not here.</p>
            <div className="lost-a">
              <Link className="btn gold" href="/">回到首页</Link>
              <Link className="btn line" href="/en/" hrefLang="en">English home</Link>
            </div>
          </main>
        </Frame>
      </body>
    </html>
  );
}
