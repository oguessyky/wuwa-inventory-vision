import { docMetadata } from '@/components/Doc';
import { Landing } from '@/components/Landing';

export const metadata = docMetadata('zh', 'index');
export default function Page() {
  return <Landing lang="zh" />;
}
