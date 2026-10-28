import { Doc, docMetadata, Moved, movedMetadata } from '@/components/Doc';
import { MOVED, pages } from '@/lib/content';

export const dynamicParams = false;
// every page, and each old address that forwards to its new one (D225: /home/ is /server/)
export const generateStaticParams = () => [
  ...pages().filter(p => p.slug !== 'index').map(p => ({ slug: p.slug })),
  ...Object.keys(MOVED).map(slug => ({ slug })),
];
export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return MOVED[slug] ? movedMetadata('zh', MOVED[slug]) : docMetadata('zh', slug);
}
export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return MOVED[slug] ? <Moved lang="zh" to={MOVED[slug]} /> : <Doc lang="zh" slug={slug} />;
}
