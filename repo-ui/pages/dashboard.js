import { useEffect, useState } from 'react';

const REFRESH_INTERVAL_MS = 60000;

export default function Dashboard() {
  const [status, setStatus] = useState('checking');
  const [payload, setPayload] = useState(null);
  const [error, setError] = useState(null);

  async function fetchStatus(signal) {
    try {
      const response = await fetch('/api/backend-status', { signal });
      if (!response.ok) {
        throw new Error(`Status request failed with ${response.status}`);
      }
      const body = await response.json();
      setStatus(body?.status || 'unknown');
      setPayload(body || null);
      setError(null);
    } catch (err) {
      if (err.name === 'AbortError') return;
      console.error(err);
      setStatus('unreachable');
      setError('Unable to reach backend status endpoint.');
    }
  }

  useEffect(() => {
    const abortController = new AbortController();
    fetchStatus(abortController.signal);

    const timer = setInterval(() => {
      const controller = new AbortController();
      fetchStatus(controller.signal);
    }, REFRESH_INTERVAL_MS);

    return () => {
      abortController.abort();
      clearInterval(timer);
    };
  }, []);

  return (
    <div className="p-6 text-sm text-muted-foreground">
      <h1 className="text-xl font-semibold text-foreground">Camarad Backend Status</h1>
      <p className="mt-3">
        This dashboard surfaces a read-only heartbeat so the public UI never proxies privileged APIs directly.
      </p>
      <div className="mt-6 rounded-xl border border-border/60 bg-surface p-5 shadow-sm">
        <div className="flex items-center justify-between text-sm">
          <span className="font-semibold text-foreground">Status</span>
          <span
            className={
              status === 'ok'
                ? 'inline-flex items-center rounded-full bg-emerald-600/20 px-3 py-1 text-xs font-semibold text-emerald-300'
                : 'inline-flex items-center rounded-full bg-amber-600/20 px-3 py-1 text-xs font-semibold text-amber-200'
            }
          >
            {status}
          </span>
        </div>
        <pre className="mt-4 max-h-80 overflow-y-auto whitespace-pre-wrap rounded-lg bg-black/30 p-4 text-xs text-foreground">
          {payload ? JSON.stringify(payload, null, 2) : 'No payload captured yet.'}
        </pre>
      </div>
      {error && <p className="mt-4 text-xs text-rose-300">{error}</p>}
    </div>
  );
}
