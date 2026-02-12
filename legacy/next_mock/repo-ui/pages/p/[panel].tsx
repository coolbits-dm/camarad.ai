import type { GetStaticPaths, GetStaticProps } from 'next';
import Head from 'next/head';
import { useRouter } from 'next/router';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { BitsOrchestratorPanel } from '@/components/bits/BitsOrchestratorPanel';
import { ChatWindow } from '@/components/chat/ChatWindow';
import { ConnectorsModal } from '@/components/connectors/ConnectorsModal';
import { BackendStatusIndicator } from '@/components/layout/BackendStatusIndicator';
import { Sidebar } from '@/components/layout/Sidebar';
import { Topbar } from '@/components/layout/Topbar';
import { PanelChatProvider } from '@/components/providers';
import { TelemetryStrip } from '@/components/layout/TelemetryStrip';
import { DEFAULT_PANEL, getPanelDefinition, isPanelKey, PANEL_DEFINITIONS, type PanelKey } from '@/lib/panels';
import fetcher from '@/lib/fetcher';
import type { TelemetrySnapshot } from '@/types/telemetry';
import { toast } from 'sonner';

type ActiveView = 'chat' | 'bits';

export default function PanelPage() {
  const router = useRouter();
  const panelParam = router.query.panel;
  const panel = useMemo<PanelKey | null>(() => {
    if (typeof panelParam !== 'string') return null;
    if (!isPanelKey(panelParam)) return null;
    return panelParam;
  }, [panelParam]);

  useEffect(() => {
    if (!router.isReady) return;
    if (!panel) {
      router.replace(`/p/${DEFAULT_PANEL}`);
    }
  }, [panel, router]);

  const [activeView, setActiveView] = useState<ActiveView>('chat');
  const [connectorsOpen, setConnectorsOpen] = useState(false);
  const [memoryCount, setMemoryCount] = useState(0);
  const [telemetry, setTelemetry] = useState<TelemetrySnapshot | null>(null);
  const [telemetryLoading, setTelemetryLoading] = useState(false);
  const telemetryStreamRef = useRef<EventSource | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const [lastTelemetryUpdate, setLastTelemetryUpdate] = useState<number | null>(null);

  const refreshTelemetry = useCallback(async () => {
    setTelemetryLoading(true);
    try {
      const snapshot = await fetcher.json<TelemetrySnapshot>('/relay/api/telemetry/full');
      setTelemetry(snapshot);
      setLastTelemetryUpdate(Date.now());
    } catch (error) {
      toast.error('Unable to load telemetry snapshot.');
    } finally {
      setTelemetryLoading(false);
    }
  }, []);

  useEffect(() => {
    setActiveView('chat');
    setConnectorsOpen(false);
    setMemoryCount(0);
    refreshTelemetry();
  }, [panel, refreshTelemetry]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    let disposed = false;

    const openStream = () => {
      if (telemetryStreamRef.current) {
        telemetryStreamRef.current.close();
        telemetryStreamRef.current = null;
      }
      let source: EventSource;
      try {
        source = new EventSource('/relay/api/telemetry/stream');
      } catch {
        return;
      }
      telemetryStreamRef.current = source;
      source.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as TelemetrySnapshot;
          setTelemetry(data);
          setLastTelemetryUpdate(Date.now());
        } catch {
          // ignore malformed telemetry payloads
        }
      };
      source.onerror = () => {
        source.close();
        if (disposed) {
          return;
        }
        if (reconnectTimerRef.current !== null) {
          window.clearTimeout(reconnectTimerRef.current);
        }
        reconnectTimerRef.current = window.setTimeout(() => {
          reconnectTimerRef.current = null;
          openStream();
        }, 2000);
      };
    };

    openStream();

    return () => {
      disposed = true;
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (telemetryStreamRef.current) {
        telemetryStreamRef.current.close();
        telemetryStreamRef.current = null;
      }
    };
  }, []);

  if (!panel) {
    return null;
  }

  const definition = getPanelDefinition(panel);

  return (
    <>
      <Head>
        <title>Camarad · {definition.label}</title>
      </Head>
      <PanelChatProvider panel={panel}>
        <div className="flex h-screen bg-background text-foreground">
          <Sidebar
            panel={panel}
            activeView={activeView}
            onSelectView={setActiveView}
            onShowConnectors={() => setConnectorsOpen(true)}
          />
          <div className="flex flex-1 flex-col min-h-0">
            <Topbar panel={panel} memoryCount={memoryCount} rightSlot={<BackendStatusIndicator />} />
            <main className="flex flex-1 flex-col min-h-0 bg-background/60 overflow-hidden">
              {activeView === 'chat' ? (
                <ChatWindow panel={panel} onMemoryCountChange={setMemoryCount} telemetry={telemetry} lastTelemetryUpdate={lastTelemetryUpdate} />
              ) : (
                <BitsOrchestratorPanel
                  panel={panel}
                  telemetry={telemetry}
                  onRefresh={refreshTelemetry}
                  loading={telemetryLoading}
                />
              )}
            </main>
            {activeView !== 'chat' && <TelemetryStrip panel={panel} telemetry={telemetry} lastUpdatedAt={lastTelemetryUpdate} />}
          </div>
        </div>
        <ConnectorsModal open={connectorsOpen} onOpenChange={setConnectorsOpen} panel={panel} />
      </PanelChatProvider>
    </>
  );
}

export const getStaticPaths: GetStaticPaths = async () => {
  const paths = PANEL_DEFINITIONS.map((panel) => ({
    params: { panel: panel.key },
  }));

  return {
    paths,
    fallback: false,
  };
};

export const getStaticProps: GetStaticProps = async ({ params }) => {
  const panelParam = typeof params?.panel === 'string' ? params.panel : null;
  if (!panelParam || !isPanelKey(panelParam)) {
    return {
      notFound: true,
    };
  }

  return {
    props: {},
  };
};
