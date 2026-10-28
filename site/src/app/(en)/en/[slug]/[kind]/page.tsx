import { Moved, movedMetadata } from '@/components/Doc';

// The Mac guides' old pages (D214), /en/guides/mac-full/ and /en/guides/mac-scanner/: their steps
// are pictures on the Mac page now (D228), so the old address forwards there.
export const dynamicParams = false;
export const generateStaticParams = () => ['mac-full', 'mac-scanner'].map(kind => ({ slug: 'guides', kind }));
export const metadata = movedMetadata('en', 'mac');
export default function Page() {
  return <Moved lang="en" to="mac" />;
}
