import type { ReactNode } from 'react';
import { ROOT_METADATA, VIEWPORT } from '@/lib/seo';
import '../site.css';

// The help site (D210) in English, under /en: its own root, so its pages say they are English
// (D222).
export const metadata = ROOT_METADATA;
export const viewport = VIEWPORT;

export default function Root({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
