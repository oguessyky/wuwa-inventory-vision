import { Moved, movedMetadata } from '@/components/Doc';

// The Mac guides' old pages (D214), /guides/mac-full/ and /guides/mac-scanner/: their steps are
// pictures on the Mac page now (D228), so the old address forwards there.
export const dynamicParams = false;
export const generateStaticParams = () => ['mac-full', 'mac-scanner'].map(kind => ({ slug: 'guides', kind }));
export const metadata = movedMetadata('zh', 'mac');
export default function Page() {
  return <Moved lang="zh" to="mac" />;
}
