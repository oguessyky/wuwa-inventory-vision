import type { ReactNode } from 'react';
import './site.css';

// The help site (D210). Chinese is the main language, as in the app; each page says its own.
export default function Root({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
