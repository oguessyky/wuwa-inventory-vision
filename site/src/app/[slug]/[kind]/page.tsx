import { MacGuide, macKinds } from '@/components/Doc';

// A Mac package's guide (D214): /guides/mac-full/ and /guides/mac-scanner/.
export const dynamicParams = false;
export const generateStaticParams = () => macKinds().map(kind => ({ slug: 'guides', kind }));
export const metadata = { title: 'Mac · WuWa Inventory Vision' };
export default async function Page({ params }: { params: Promise<{ slug: string; kind: string }> }) {
  return <MacGuide lang="zh" kind={(await params).kind} />;
}
