import { Doc, docMetadata } from '@/components/Doc';

export const metadata = docMetadata('en', 'index');
export default function Page() {
  return <Doc lang="en" slug="index" />;
}
