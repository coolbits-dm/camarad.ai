import clsx from 'clsx';
import { useEffect, useMemo, useState } from 'react';

import { useFetcherMetrics } from '@/components/providers';
import type { PanelKey } from '@/lib/panels';
import type { TelemetrySnapshot } from '@/types/telemetry';

interface TelemetryStripProps {
  panel: PanelKey;
  telemetry: TelemetrySnapshot | null;
  className?: string;
  lastUpdatedAt?: number | null;
}

export function TelemetryStrip({ panel, telemetry, className, lastUpdatedAt }: TelemetryStripProps) {
  const { lastLatency, lastMeta } = useFetcherMetrics();
  const balance = telemetry?.ledger?.metrics?.panel_balances?.[panel];
  const healthStatus = telemetry?.health?.status ?? 'online';
  const serviceSnapshot = telemetry?.health?.services ?? {};
  const primaryService = Object.entries(serviceSnapshot)[0];
  const [now, setNow] = useState(() => (typeof Date.now === 'function' ? Date.now() : 0));

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const id = window.setInterval(() => {
      setNow(Date.now());
    }, 1000);
    return () => window.clearInterval(id);
  }, []);

  const secondsSinceUpdate = useMemo(() => {
    if (!lastUpdatedAt) {
      return null;
    }
    return Math.max(0, Math.round((now - lastUpdatedAt) / 1000));
  }, [lastUpdatedAt, now]);

  let statusClass = 'bg-success';
  if (secondsSinceUpdate === null) {
    statusClass = 'bg-muted/60';
  } else if (secondsSinceUpdate > 15) {
    statusClass = 'bg-danger';
  } else if (secondsSinceUpdate > 3) {
    statusClass = 'bg-amber-400';
  } else if (healthStatus !== 'ok' && healthStatus !== 'online' && healthStatus !== 'ready') {
    statusClass = 'bg-amber-400';
  }

  const statusLabel =
    secondsSinceUpdate === null
      ? 'No telemetry'
      : `${healthStatus === 'ok' ? 'Healthy' : healthStatus} · ${secondsSinceUpdate}s ago`;

  return (
    <footer
      className={clsx(
        'flex flex-wrap items-center gap-4 bg-background/90 px-4 py-1.5 text-xs text-muted-foreground sm:px-6',
        className,
      )}
    >
      <div className="flex items-center gap-2 whitespace-nowrap">
        <span className={clsx('h-2 w-2 rounded-full', statusClass)} aria-hidden />
        <span className="font-semibold text-foreground">Status</span>
        <span>{statusLabel}</span>
      </div>
      <div className="flex items-center gap-2 whitespace-nowrap">
        <span className="font-semibold text-foreground">Latency</span>
        <span>
          {typeof lastLatency === 'number' ? `${Math.round(lastLatency)} ms` : '—'}
          {lastMeta?.status && <span className="text-muted-foreground/70"> · {lastMeta.status}</span>}
        </span>
      </div>
      <div className="flex items-center gap-2 whitespace-nowrap">
        <span className="font-semibold text-foreground">Balance</span>
        <span>
          {typeof balance === 'number'
            ? balance.toLocaleString(undefined, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })
            : '—'}
        </span>
      </div>
      <div className="flex items-center gap-2 whitespace-nowrap">
        <span className="font-semibold text-foreground">Service</span>
        <span className="capitalize">{healthStatus}</span>
        {primaryService && (
          <span className="text-muted-foreground/70">
            · {primaryService[0]} {primaryService[1]}
          </span>
        )}
      </div>
    </footer>
  );
}
