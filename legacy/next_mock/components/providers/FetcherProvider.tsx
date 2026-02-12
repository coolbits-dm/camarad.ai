import { createContext, useContext, useEffect, useMemo, useState } from 'react';

import fetcher, { type LatencyMeta } from '@/lib/fetcher';

interface FetcherMetrics {
  lastLatency: number | null;
  lastMeta: LatencyMeta | null;
}

const FetcherMetricsContext = createContext<FetcherMetrics | undefined>(undefined);

export function FetcherProvider({ children }: { children: React.ReactNode }) {
  const [lastLatency, setLastLatency] = useState<number | null>(null);
  const [lastMeta, setLastMeta] = useState<LatencyMeta | null>(null);

  useEffect(() => {
    const latest = fetcher.getLatestLatency();
    if (latest.latency !== null) {
      setLastLatency(latest.latency);
      setLastMeta(latest.meta);
    }
    const unsubscribe = fetcher.onLatency((latency, meta) => {
      setLastLatency(latency);
      setLastMeta(meta);
    });
    return unsubscribe;
  }, []);

  const value = useMemo<FetcherMetrics>(() => ({ lastLatency, lastMeta }), [lastLatency, lastMeta]);

  return <FetcherMetricsContext.Provider value={value}>{children}</FetcherMetricsContext.Provider>;
}

export function useFetcherMetrics() {
  const context = useContext(FetcherMetricsContext);
  if (!context) {
    throw new Error('useFetcherMetrics must be used within FetcherProvider');
  }
  return context;
}
