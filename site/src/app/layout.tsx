import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import './site.css';

// The help site (D210). Chinese is the main language, as in the app; each page says its own.
// Google Search Console knows the site by this tag (and by the file beside it, D214).
export const metadata: Metadata = {
  metadataBase: new URL('https://oguessyky.github.io/wuwa-inventory-vision/'),
  verification: { google: 'AqQQUjncIGVuVD3R_KTd3kd9AgV9BQuQMmdkbDTu-Bs' },
};

export default function Root({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
