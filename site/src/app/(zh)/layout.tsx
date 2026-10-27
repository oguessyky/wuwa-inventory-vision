import type { ReactNode } from 'react';
import { ROOT_METADATA, VIEWPORT } from '@/lib/seo';
import '../site.css';

// The help site (D210), in Chinese -- the main language, as in the app. Each language is its own
// root, so a page says the language it is written in to a search engine (D222).
export const metadata = ROOT_METADATA;
export const viewport = VIEWPORT;

export default function Root({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
