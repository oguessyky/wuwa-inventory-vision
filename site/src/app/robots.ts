import type { MetadataRoute } from 'next';
import { SITE } from '@/lib/seo';

// robots.txt (D222): every page may be read, and the sitemap is named. Written once at build.
// A crawler looks for robots.txt only at a domain's root -- oguessyky.github.io/, a site of its
// own -- so the sitemap is also given to Search Console directly; this file says it for the rest.
export const dynamic = 'force-static';

export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: '*', allow: '/' },
    sitemap: `${SITE}/sitemap.xml`,
  };
}
