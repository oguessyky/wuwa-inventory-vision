import { Doc, docMetadata } from '@/components/Doc';
import { pages } from '@/lib/content';

export const dynamicParams = false;
// every page
export const generateStaticParams = () => [
  ...pages().filter(p => p.slug !== 'index').map(p => ({ slug: p.slug })),
];
export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return docMetadata('zh', slug);
}
export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return <Doc lang="zh" slug={slug} />;
}
