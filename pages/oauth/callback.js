import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';

export default function OAuthCallback() {
  const router = useRouter();
  const [status, setStatus] = useState('Processing OAuth callback…');
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!router.isReady) return;
    const normalize = (value) => (Array.isArray(value) ? value[0] : value);
    const code = normalize(router.query.code);
    const state = normalize(router.query.state);
    let provider = normalize(router.query.provider);
    let userId = normalize(router.query.user_id) || 'admin';

    if (typeof window !== 'undefined') {
      if (!provider) {
        provider = sessionStorage.getItem('oauthProvider') || provider;
      }
      const storedUser = sessionStorage.getItem('oauthUserId');
      if (!router.query.user_id && storedUser) {
        userId = storedUser;
      }
    }

    if (!code || !state || !provider) {
      console.error('Missing OAuth parameters', { code, state, provider, routerQuery: router.query });
      setError('Missing OAuth parameters.');
      return;
    }

    const finalize = async () => {
      try {
        const res = await fetch('/relay/api/oauth/callback', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ provider, user_id: userId, code, state, redirect_uri: window.location.origin + router.pathname }),
        });
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data?.detail || JSON.stringify(data));
        }
        setStatus(`Connector ${provider} linked successfully.`);
        setTimeout(() => router.replace('/connectors'), 2000);
      } catch (err) {
        console.error(err);
        setError(`OAuth callback failed: ${err.message}`);
      } finally {
        if (typeof window !== 'undefined') {
          sessionStorage.removeItem('oauthProvider');
          sessionStorage.removeItem('oauthUserId');
        }
      }
    };

    finalize();
  }, [router]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-surface-dark p-6 text-slate-100">
      <div className="max-w-md rounded-2xl bg-surface p-8 text-center shadow-xl">
        <h1 className="text-xl font-semibold">OAuth Callback</h1>
        {error ? (
          <p className="mt-4 text-sm text-rose-400">{error}</p>
        ) : (
          <p className="mt-4 text-sm text-slate-300">{status}</p>
        )}
      </div>
    </main>
  );
}
