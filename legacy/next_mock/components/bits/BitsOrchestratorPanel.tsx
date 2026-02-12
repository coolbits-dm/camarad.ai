import { Loader2, RefreshCcw, Rocket, ShieldCheck, Sparkles } from 'lucide-react';
import clsx from 'clsx';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';

import fetcher from '@/lib/fetcher';
import type { PanelKey } from '@/lib/panels';
import type { TelemetryEvent, TelemetrySnapshot } from '@/types/telemetry';
import { formatDateTime } from '@/lib/utils';

interface BitsOrchestratorPanelProps {
  panel: PanelKey;
  telemetry: TelemetrySnapshot | null;
  onRefresh: () => Promise<void>;
  loading?: boolean;
}

const TRIGGERS: Array<{ label: string; type: string; description: string }> = [
  {
    label: 'Refresh Metrics',
    type: 'sync:refresh-metrics',
    description: 'Sync the agency metrics ledger immediately.',
  },
  {
    label: 'Ledger Reconcile',
    type: 'ledger:reconcile',
    description: 'Run a reconciliation cycle for balances.',
  },
  {
    label: 'Connector Check',
    type: 'connector:check',
    description: 'Verify upstream connectors and ingest deltas.',
  },
];

function renderLogTail(logTail: TelemetrySnapshot['log_tail']) {
  if (!logTail) return [];
  if (Array.isArray(logTail)) return logTail;
  return String(logTail).split('\n');
}

export function BitsOrchestratorPanel({ panel, telemetry, onRefresh, loading = false }: BitsOrchestratorPanelProps) {
  const [triggering, setTriggering] = useState<string | null>(null);
  const [initialised, setInitialised] = useState(false);

  useEffect(() => {
    if (!initialised) {
      setInitialised(true);
      onRefresh().catch(() => undefined);
    }
  }, [initialised, onRefresh]);

  const events = useMemo<TelemetryEvent[]>(() => {
    return telemetry?.events?.slice(0, 20) ?? [];
  }, [telemetry]);

  const panelBalance = telemetry?.ledger?.metrics?.panel_balances?.[panel];
  const logLines = useMemo(() => renderLogTail(telemetry?.log_tail), [telemetry]);

  const triggerEvent = useCallback(
    async (type: string) => {
      setTriggering(type);
      try {
        await fetcher.json('/relay/api/events', {
          method: 'POST',
          body: { scope: 'agency', type },
        });
        toast.success(`Event queued: ${type}`);
        await onRefresh();
      } catch (error) {
        toast.error(`Unable to queue ${type}.`);
      } finally {
        setTriggering(null);
      }
    },
    [onRefresh],
  );

  return (
    <section className="flex min-h-[calc(100vh-5rem)] flex-1 flex-col">
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 px-4 py-10 sm:px-6">
          <header className="rounded-3xl border border-border/50 bg-surface-muted/60 px-6 py-6 shadow">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.4em] text-muted-foreground/70">Bits Orchestrator</p>
                <h2 className="mt-2 text-2xl font-semibold text-foreground">Automation control for {panel}</h2>
                <p className="mt-2 text-sm text-muted-foreground">
                  Queue jobs, inspect the telemetry feed, and keep the agency orchestrator humming.
                </p>
              </div>
              <div className="flex items-center gap-3">
                {typeof panelBalance === 'number' && (
                  <div className="rounded-2xl border border-accent/30 bg-accent/10 px-4 py-2 text-sm text-accent shadow-inner">
                    Balance · {panelBalance.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </div>
                )}
                <button
                  type="button"
                  onClick={() => onRefresh()}
                  disabled={loading}
                  className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-background/80 px-4 py-2 text-sm font-semibold text-foreground shadow hover:border-accent/60 hover:text-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <RefreshCcw className="h-4 w-4" aria-hidden />}
                  Refresh snapshot
                </button>
              </div>
            </div>
          </header>

          <section className="grid gap-4 md:grid-cols-3">
            {TRIGGERS.map((trigger) => (
              <button
                key={trigger.type}
                type="button"
                onClick={() => triggerEvent(trigger.type)}
                disabled={triggering === trigger.type}
                className={clsx(
                  'flex flex-col items-start gap-3 rounded-2xl border border-border/50 bg-surface-muted/60 p-5 text-left transition hover:border-accent/40 hover:bg-surface-muted/80 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60',
                )}
              >
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-accent/15 text-accent">
                  {trigger.type === 'sync:refresh-metrics' && <Sparkles className="h-5 w-5" aria-hidden />}
                  {trigger.type === 'ledger:reconcile' && <ShieldCheck className="h-5 w-5" aria-hidden />}
                  {trigger.type === 'connector:check' && <Rocket className="h-5 w-5" aria-hidden />}
                </div>
                <div>
                  <h3 className="text-base font-semibold text-foreground">{trigger.label}</h3>
                  <p className="mt-1 text-sm text-muted-foreground">{trigger.description}</p>
                </div>
                <span className="inline-flex items-center gap-2 text-xs font-semibold text-accent">
                  {triggering === trigger.type ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
                      Dispatching…
                    </>
                  ) : (
                    'Queue event'
                  )}
                </span>
              </button>
            ))}
          </section>

          <section className="rounded-3xl border border-border/50 bg-surface-muted/60 px-6 py-6 shadow">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-lg font-semibold text-foreground">Recent Events</h3>
              <span className="text-xs text-muted-foreground">Showing last {events.length} entries</span>
            </div>
            {events.length === 0 ? (
              <p className="mt-4 text-sm text-muted-foreground">No recent events queued for this scope yet.</p>
            ) : (
              <ul className="mt-4 space-y-3">
                {events.map((event, index) => (
                  <li
                    key={event.id ?? `${event.type}-${index}`}
                    className="rounded-2xl border border-border/40 bg-background/60 px-4 py-3 text-sm text-foreground"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-semibold text-accent">{event.type}</span>
                      <span className="text-xs text-muted-foreground">
                        {event.enqueued_at ? formatDateTime(event.enqueued_at) : 'Just now'}
                      </span>
                    </div>
                    {event.status && (
                      <p className="mt-1 text-xs text-muted-foreground">Status · {event.status}</p>
                    )}
                    {event.scope && (
                      <p className="text-xs text-muted-foreground/70">Scope · {event.scope}</p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="rounded-3xl border border-border/50 bg-surface-muted/60 px-6 py-6 shadow">
            <h3 className="text-lg font-semibold text-foreground">Orchestrator Log</h3>
            <div className="mt-4 max-h-64 overflow-y-auto rounded-2xl border border-border/40 bg-background/60 px-4 py-3 text-xs font-mono text-muted-foreground/80">
              {logLines.map((line, index) => (
                <p key={index} className="whitespace-pre-wrap">
                  {line}
                </p>
              ))}
              {logLines.length === 0 && (
                <p>No log output for this window.</p>
              )}
            </div>
          </section>
        </div>
      </div>
    </section>
  );
}
