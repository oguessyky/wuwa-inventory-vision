import { Doc, docMetadata } from '@/components/Doc';
import { pages } from '@/lib/content';

export const dynamicParams = false;
export const generateStaticParams = () => pages().filter(p => p.slug !== 'index').map(p => ({ slug: p.slug }));
export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  return docMetadata('zh', (await params).slug);
}
export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  return <Doc lang="zh" slug={(await params).slug} />;
}
