import { useEffect, useState } from 'react';
import { HEALTHCHECK_URL } from '@/lib/config';

type Status = 'checking' | 'ok' | 'unreachable';

interface BackendStatusResponse {
  status: string;
  target: string;
  response?: unknown;
  error?: string;
}

const POLL_INTERVAL_MS = 60000;

const DEFAULT_BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_STATUS_URL ||
  HEALTHCHECK_URL;

export function BackendStatusIndicator() {
  const [status, setStatus] = useState<Status>('checking');
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | null>(null);

  useEffect(() => {
    let isMounted = true;

    const fetchStatus = async () => {
      try {
  const response = await fetch(DEFAULT_BACKEND_URL, { cache: 'no-store' });
        if (!response.ok) {
          throw new Error(`Status request failed with ${response.status}`);
        }
        const text = await response.text();
        let body: unknown = undefined;
        try {
          body = text ? JSON.parse(text) : null;
        } catch {
          body = { raw: text };
        }
        if (!isMounted) return;
        let derivedStatus = response.ok ? 'ok' : 'unreachable';
        if (response.ok && body && typeof body === 'object' && 'status' in body && typeof (body as { status?: unknown }).status === 'string') {
          derivedStatus = (body as { status: string }).status;
        }
        const normalized = derivedStatus === 'ok' ? 'ok' : derivedStatus === 'unreachable' ? 'unreachable' : 'ok';
        setStatus(normalized);
        setLastUpdatedAt(Date.now());
      } catch (error) {
        console.error('backend-status', error);
        if (!isMounted) return;
        setStatus('unreachable');
        setLastUpdatedAt(Date.now());
      }
    };

    fetchStatus();
    const timer = setInterval(fetchStatus, POLL_INTERVAL_MS);

    return () => {
      isMounted = false;
      clearInterval(timer);
    };
  }, []);

  const label =
    status === 'checking'
      ? 'Checking…'
      : status === 'ok'
        ? 'Backend online'
        : 'Backend unreachable';

  const tooltip =
    lastUpdatedAt !== null ? `Last checked ${new Date(lastUpdatedAt).toLocaleTimeString()}` : 'No status received yet.';

  const badgeClasses =
    status === 'ok'
      ? 'bg-emerald-600/15 text-emerald-300 border-emerald-500/40'
      : status === 'checking'
        ? 'bg-sky-600/15 text-sky-200 border-sky-500/40'
        : 'bg-rose-600/15 text-rose-300 border-rose-500/40';

  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold transition ${badgeClasses}`}
      title={tooltip}
    >
      <span className="inline-flex h-2 w-2 items-center justify-center">
        <span
          className={`inline-block h-2 w-2 rounded-full ${
            status === 'ok' ? 'bg-emerald-400' : status === 'checking' ? 'bg-sky-300' : 'bg-rose-400'
          }`}
        />
      </span>
      {label}
    </span>
  );
}
