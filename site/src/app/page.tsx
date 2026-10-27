import { Doc, docMetadata } from '@/components/Doc';

export const metadata = docMetadata('zh', 'index');
export default function Page() {
  return <Doc lang="zh" slug="index" />;
}
