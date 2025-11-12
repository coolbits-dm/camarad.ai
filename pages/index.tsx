import { useEffect } from 'react';
import { useRouter } from 'next/router';

import { DEFAULT_PANEL } from '@/lib/panels';

export default function IndexPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace(`/p/${DEFAULT_PANEL}`);
  }, [router]);

  return null;
}
