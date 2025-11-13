import * as Dialog from '@radix-ui/react-dialog';
import { CheckCircle2, Loader2, Plug, RefreshCcw, XCircle } from 'lucide-react';
import clsx from 'clsx';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';

import fetcher from '@/lib/fetcher';
import type { PanelKey } from '@/lib/panels';
import type { ConnectorProviderState, ConnectorStatusResponse } from '@/types/connectors';
import { formatDateTime } from '@/lib/utils';

export interface ConnectorsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  panel?: PanelKey;
}

interface ConnectorPreset {
  provider: string;
  label: string;
  description: string;
  accentClass: string;
}

const CONNECTOR_PRESETS: ConnectorPreset[] = [
  {
    provider: 'google',
    label: 'Google',
    description: 'Ads, analytics, and workspace signals.',
    accentClass: 'from-emerald-500/30 to-emerald-500/10',
  },
  {
    provider: 'meta',
    label: 'Meta',
    description: 'Campaign insights and creative diagnostics.',
    accentClass: 'from-sky-500/30 to-sky-500/10',
  },
  {
    provider: 'linkedin',
    label: 'LinkedIn',
    description: 'B2B attribution and audience sync.',
    accentClass: 'from-cyan-500/30 to-cyan-500/10',
  },
  {
    provider: 'tiktok',
    label: 'TikTok',
    description: 'Short-form content metrics and spend.',
    accentClass: 'from-rose-500/30 to-rose-500/10',
  },
];

function normalizeProviders(response: ConnectorStatusResponse | null): ConnectorProviderState[] {
  const map = new Map<string, ConnectorProviderState>();

  if (response?.providers) {
    response.providers.forEach((provider) => {
      const connected =
        typeof provider.connected === 'boolean'
          ? provider.connected
          : provider.status === 'connected';
      const status = provider.status ?? (connected ? 'connected' : 'disconnected');
      map.set(provider.provider, {
        provider: provider.provider,
        displayName:
          provider.display_name ?? provider.provider.replace(/\b\w/g, (char) => char.toUpperCase()),
        status,
        connected,
        lastSyncedAt:
          (provider.last_synced_at as string | undefined) ??
          (provider.synced_at as string | undefined),
        accountName: (provider.account_name as string | undefined) ?? (provider.account as string | undefined),
        details: provider,
      });
    });
  }

  CONNECTOR_PRESETS.forEach((preset) => {
    if (!map.has(preset.provider)) {
      map.set(preset.provider, {
        provider: preset.provider,
        displayName: preset.label,
        status: 'disconnected',
        connected: false,
      });
    } else {
      const existing = map.get(preset.provider)!;
      existing.displayName = existing.displayName || preset.label;
    }
  });

  return Array.from(map.values()).sort((a, b) => a.displayName.localeCompare(b.displayName));
}

export function ConnectorsModal({ open, onOpenChange, panel }: ConnectorsModalProps) {
  const [loading, setLoading] = useState(false);
  const [busyProvider, setBusyProvider] = useState<string | null>(null);
  const [providers, setProviders] = useState<ConnectorProviderState[]>(() => normalizeProviders(null));

  const fetchStatus = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetcher.json<ConnectorStatusResponse>('/relay/api/oauth/status');
      setProviders(normalizeProviders(response));
    } catch (error) {
      toast.error('Unable to load connector status.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) {
      fetchStatus();
    }
  }, [open, fetchStatus]);

  const presetsByProvider = useMemo(() => {
    const map = new Map(CONNECTOR_PRESETS.map((preset) => [preset.provider, preset]));
    return map;
  }, []);

  const handleRefresh = async (provider: ConnectorProviderState) => {
    setBusyProvider(provider.provider);
    try {
      await fetcher.json('/relay/api/oauth/status', {
        method: 'POST',
        body: { provider: provider.provider, panel },
      });
      toast.success(`Status refreshed for ${provider.displayName}.`);
      await fetchStatus();
    } catch (error) {
      toast.error(`Unable to refresh ${provider.displayName}.`);
    } finally {
      setBusyProvider(null);
    }
  };

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-background/70 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=open]:fade-in-0 data-[state=closed]:fade-out-0" />
        <Dialog.Content className="fixed inset-0 z-50 flex items-center justify-center p-4 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=open]:zoom-in-95 data-[state=closed]:zoom-out-95">
          <div className="w-full max-w-3xl rounded-3xl border border-border/60 bg-surface shadow-2xl">
            <header className="flex items-start gap-4 border-b border-border/40 px-8 py-6">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-accent/15 text-accent">
                <Plug className="h-6 w-6" aria-hidden />
              </div>
              <div>
                <Dialog.Title className="text-lg font-semibold text-foreground">Connectors</Dialog.Title>
                <Dialog.Description className="mt-1 text-sm text-muted-foreground">
                  Keep external platforms in sync with your Camarad panels. Connectors refresh in place until the OAuth
                  flow ships.
                </Dialog.Description>
              </div>
            </header>
            <div className="max-h-[480px] overflow-y-auto px-8 py-6">
              {loading && (
                <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-border/50 px-3 py-1 text-xs text-muted-foreground">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
                  Checking connector status…
                </div>
              )}
              <div className="grid gap-4 md:grid-cols-2">
                {providers.map((provider) => {
                  const preset = presetsByProvider.get(provider.provider);
                  const isBusy = busyProvider === provider.provider;
                  const connected = provider.connected;
                  const detailDescriptionRaw = provider.details?.['description'];
                  const detailDescription =
                    typeof detailDescriptionRaw === 'string' ? (detailDescriptionRaw as string) : undefined;
                  const statusBadge = connected ? (
                    <span className="inline-flex items-center gap-2 rounded-full border border-emerald-400/40 bg-emerald-400/10 px-3 py-1 text-xs font-semibold text-emerald-300">
                      <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
                      Connected
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-2 rounded-full border border-rose-400/40 bg-rose-400/10 px-3 py-1 text-xs font-semibold text-rose-300">
                      <XCircle className="h-3.5 w-3.5" aria-hidden />
                      Disconnected
                    </span>
                  );

                  return (
                    <div
                      key={provider.provider}
                      className={clsx(
                        'group relative overflow-hidden rounded-2xl border border-border/50 bg-surface-muted/60 p-5 transition hover:border-accent/40 hover:bg-surface-muted/80',
                      )}
                    >
                      <div
                        className={clsx(
                          'pointer-events-none absolute inset-0 -z-10 bg-gradient-to-br opacity-0 transition group-hover:opacity-100',
                          preset?.accentClass,
                        )}
                        aria-hidden
                      />
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <h3 className="text-base font-semibold text-foreground">{provider.displayName}</h3>
                          <p className="mt-1 text-sm text-muted-foreground">
                            {preset?.description ?? detailDescription ?? 'No description available.'}
                          </p>
                        </div>
                        {statusBadge}
                      </div>
                      <dl className="mt-4 space-y-2 text-xs text-muted-foreground">
                        {provider.accountName && (
                          <div className="flex items-center justify-between gap-2">
                            <dt>Account</dt>
                            <dd className="font-medium text-foreground">{provider.accountName}</dd>
                          </div>
                        )}
                        {provider.lastSyncedAt && (
                          <div className="flex items-center justify-between gap-2">
                            <dt>Last sync</dt>
                            <dd className="font-medium text-foreground">{formatDateTime(provider.lastSyncedAt)}</dd>
                          </div>
                        )}
                      </dl>
                      <button
                        type="button"
                        onClick={() => handleRefresh(provider)}
                        disabled={isBusy}
                        className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-full border border-border/60 bg-background/80 px-4 py-2 text-sm font-semibold text-foreground shadow transition hover:border-accent/60 hover:text-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {isBusy ? (
                          <>
                            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                            Updating…
                          </>
                        ) : (
                          <>
                            <RefreshCcw className="h-4 w-4" aria-hidden />
                            {connected ? 'Refresh status' : 'Connect'}
                          </>
                        )}
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
            <footer className="flex items-center justify-between gap-3 border-t border-border/40 px-8 py-4">
              <p className="text-xs text-muted-foreground">OAuth hand-off coming soon. Manual refresh will simulate connect/disconnect.</p>
              <Dialog.Close className="rounded-full px-4 py-2 text-sm font-semibold text-muted-foreground hover:bg-surface-muted/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2">
                Close
              </Dialog.Close>
            </footer>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
