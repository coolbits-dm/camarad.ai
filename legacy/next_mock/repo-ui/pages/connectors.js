import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';

const PROVIDERS = [
  { key: 'google', name: 'Google Ads' },
  { key: 'meta', name: 'Meta (Facebook)' },
  { key: 'linkedin', name: 'LinkedIn' },
  { key: 'slack', name: 'Slack' },
];

const USER_ID = 'admin';

export default function Connectors() {
  const [statusMap, setStatusMap] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const callbackUrl = process.env.NEXT_PUBLIC_OAUTH_CALLBACK || 'https://api.camarad.ai/oauth/callback';

  const fetchStatuses = useCallback(async () => {
    try {
      const results = await Promise.all(
        PROVIDERS.map(async (provider) => {
          const res = await fetch('/relay/api/oauth/status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ provider: provider.key, user_id: USER_ID }),
          });
          if (!res.ok) {
            throw new Error(`Status fetch failed for ${provider.key}`);
          }
          return res.json();
        })
      );
      const map = {};
      results.forEach((payload) => {
        map[payload.provider] = payload;
      });
      setStatusMap(map);
      setError(null);
    } catch (err) {
      console.error(err);
      setError('Unable to load connector status.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatuses();
  }, [fetchStatuses]);

  const handleConnect = useCallback(async (provider) => {
    setError(null);
    try {
      const res = await fetch('/relay/api/oauth/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, user_id: USER_ID, redirect_uri: callbackUrl }),
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail);
      }
      const data = await res.json();
      if (typeof window !== 'undefined') {
        sessionStorage.setItem('oauthProvider', provider);
        sessionStorage.setItem('oauthUserId', USER_ID);
      }
      window.location.href = data.authorize_url;
    } catch (err) {
      console.error(err);
      setError(`Failed to initiate OAuth for ${provider}.`);
    }
  }, [callbackUrl]);

  const handleRevoke = useCallback(async (provider) => {
    try {
      const res = await fetch('/relay/api/oauth/revoke', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, user_id: USER_ID }),
      });
      if (!res.ok) {
        throw new Error('Revoke failed');
      }
      await fetchStatuses();
    } catch (err) {
      console.error(err);
      setError(`Failed to revoke ${provider} connection.`);
    }
  }, [fetchStatuses]);

  const cards = useMemo(
    () =>
      PROVIDERS.map((provider) => {
        const payload = statusMap[provider.key];
        const connected = payload?.connected;
        return (
          <div key={provider.key} className="rounded-2xl bg-surface p-6 shadow-lg">
            <h2 className="text-lg font-semibold text-slate-100">{provider.name}</h2>
            <p className="mt-2 text-sm text-slate-400">Provider key: {provider.key}</p>
            <div className="mt-4 flex items-center gap-2">
              <span
                className={`rounded-full px-3 py-1 text-xs font-semibold ${
                  connected ? 'bg-emerald-500/20 text-emerald-300' : 'bg-slate-600/40 text-slate-300'
                }`}
              >
                {connected ? 'Connected' : 'Not connected'}
              </span>
              {payload?.expires_at && (
                <span className="text-xs text-slate-400">Expires: {payload.expires_at}</span>
              )}
            </div>
            <div className="mt-6 flex gap-3">
              <button
                onClick={() => handleConnect(provider.key)}
                className="rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-slate-900 shadow"
              >
                {connected ? 'Reconnect' : 'Connect'}
              </button>
              {connected && (
                <button
                  onClick={() => handleRevoke(provider.key)}
                  className="rounded-xl border border-slate-600 px-4 py-2 text-sm text-slate-300 transition hover:border-rose-400 hover:text-rose-300"
                >
                  Revoke
                </button>
              )}
            </div>
          </div>
        );
      }),
    [statusMap, handleConnect, handleRevoke]
  );

  return (
    <main className="min-h-screen bg-surface-dark p-6 text-slate-100">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <header className="flex flex-col gap-2">
          <h1 className="text-3xl font-semibold tracking-tight">Connector Control Center</h1>
          <p className="text-sm text-slate-400">
            Manage OAuth integrations for the Camarad ecosystem. Authenticating will redirect via {callbackUrl}.
          </p>
          <div className="text-xs text-slate-500">
            <Link href="/dashboard" className="text-accent">Back to dashboard</Link>
          </div>
          {error && <p className="text-sm text-rose-400">{error}</p>}
        </header>

        {loading ? (
          <div className="rounded-2xl bg-surface p-8 text-center text-slate-300">Loading connector data…</div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">{cards}</div>
        )}
      </div>
    </main>
  );
}
