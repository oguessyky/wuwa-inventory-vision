import type { MetadataRoute } from 'next';
import { address, pages, type Lang } from '@/lib/content';

// Every page of the help site for search engines (D214): each in Chinese, with its English page
// named beside it, and the other way round. Written once at build, as a plain sitemap.xml.
export const dynamic = 'force-static';

const SITE = 'https://oguessyky.github.io/wuwa-inventory-vision';

export default function sitemap(): MetadataRoute.Sitemap {
  const built = new Date();
  const at = (path: string) => `${SITE}${path}`;
  const both = (zh: string, en: string, priority: number): MetadataRoute.Sitemap =>
    (['zh', 'en'] as Lang[]).map(lang => ({
      url: at(lang === 'en' ? en : zh),
      lastModified: built,                     // when this build was made (D222)
      changeFrequency: 'weekly',
      priority,
      alternates: { languages: { 'zh-CN': at(zh), en: at(en) } },
    }));
  return [
    ...pages().flatMap(p => both(address('zh', p.slug), address('en', p.slug), p.slug === 'index' ? 1 : 0.7)),
  ];
}
