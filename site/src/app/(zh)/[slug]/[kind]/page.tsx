import { MacGuide, macKinds, macMetadata } from '@/components/Doc';

// A Mac package's guide (D214): /guides/mac-full/ and /guides/mac-scanner/.
export const dynamicParams = false;
export const generateStaticParams = () => macKinds().map(kind => ({ slug: 'guides', kind }));
export async function generateMetadata({ params }: { params: Promise<{ slug: string; kind: string }> }) {
  return macMetadata('zh', (await params).kind);
}
export default async function Page({ params }: { params: Promise<{ slug: string; kind: string }> }) {
  return <MacGuide lang="zh" kind={(await params).kind} />;
}
