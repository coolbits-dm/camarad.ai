import { useEffect, useMemo, useState } from 'react';
import Head from 'next/head';
import { getHealth, ping } from '@/lib/api';
import StatusBadge from '@/components/StatusBadge';

export default function TestPage() {
  const [health, setHealth] = useState(null);
  const [loadingHealth, setLoadingHealth] = useState(false);
  const [message, setMessage] = useState('Hello Camarad');
  const [pingResult, setPingResult] = useState(null);
  const [pingError, setPingError] = useState(null);
  const [pingLoading, setPingLoading] = useState(false);

  const serviceName = useMemo(
    () => process.env.NEXT_PUBLIC_SERVICE_NAME || process.env.SERVICE_NAME || 'Camarad UI',
    []
  );

  useEffect(() => {
    let cancelled = false;

    async function fetchHealth() {
      setLoadingHealth(true);
      try {
        const response = await getHealth();
        if (!cancelled) {
          setHealth(response);
        }
      } catch (error) {
        if (!cancelled) {
          setHealth({ status: 'error', detail: error.details || error.message });
        }
      } finally {
        if (!cancelled) {
          setLoadingHealth(false);
        }
      }
    }

    fetchHealth();
    return () => {
      cancelled = true;
    };
  }, []);

  const handlePing = async (event) => {
    event.preventDefault();
    setPingLoading(true);
    setPingError(null);
    try {
      const response = await ping(message);
      setPingResult(response);
    } catch (error) {
      setPingError(error.details || error.message);
      setPingResult(null);
    } finally {
      setPingLoading(false);
    }
  };

  return (
    <>
      <Head>
        <title>{serviceName} · Relay Test</title>
      </Head>
      <main className="min-h-screen bg-surface-dark p-6 text-slate-100">
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
          <header className="rounded-3xl bg-surface p-8 shadow-xl">
            <h1 className="text-3xl font-semibold tracking-tight">Relay Diagnostics</h1>
            <p className="mt-2 text-sm text-slate-300">
              Confirm that the Camarad UI can reach the cbLM relay.
            </p>
            <dl className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <StatusBadge
                label="Environment"
                value={process.env.NEXT_PUBLIC_ENV || process.env.ENV || 'dev'}
                tone="text-slate-100"
              />
              <StatusBadge
                label="Health"
                value={loadingHealth ? 'Checking…' : JSON.stringify(health)}
                tone={loadingHealth ? 'text-sky-300' : 'text-emerald-400'}
              />
            </dl>
          </header>

          <section className="rounded-3xl bg-surface p-8 shadow-xl">
            <h2 className="text-2xl font-semibold">Ping the Relay</h2>
            <form className="mt-4 space-y-4" onSubmit={handlePing}>
              <label className="block text-sm font-medium text-slate-200" htmlFor="message">
                Message
              </label>
              <input
                id="message"
                type="text"
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                className="w-full rounded-xl border border-surface-light bg-surface-light/70 px-4 py-3 text-slate-100 placeholder:text-slate-500 focus:border-accent focus:outline-none"
                placeholder="Send something to the relay"
                required
              />
              <div className="flex items-center gap-3">
                <button
                  type="submit"
                  disabled={pingLoading}
                  className="inline-flex items-center justify-center rounded-xl bg-accent px-5 py-2 text-sm font-semibold text-slate-950 shadow-lg shadow-accent/30 transition hover:bg-sky-300 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {pingLoading ? 'Sending…' : 'Ping Relay'}
                </button>
                {pingError && <p className="text-sm text-rose-400">{pingError}</p>}
              </div>
            </form>
            <div className="mt-6">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Response</h3>
              <pre className="mt-2 max-h-60 overflow-auto rounded-2xl bg-surface-light p-4 text-xs text-slate-200">
                {pingResult ? JSON.stringify(pingResult, null, 2) : 'No response yet.'}
              </pre>
            </div>
          </section>
        </div>
      </main>
    </>
  );
}
