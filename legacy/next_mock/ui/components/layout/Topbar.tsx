import { Menu } from 'lucide-react';
import { type ReactNode, useMemo } from 'react';

import { getPanelDefinition, type PanelKey } from '@/lib/panels';

interface TopbarProps {
  panel: PanelKey;
  memoryCount?: number;
  onToggleSidebar?: () => void;
  rightSlot?: ReactNode;
}

export function Topbar({ panel, memoryCount, onToggleSidebar, rightSlot }: TopbarProps) {
  const definition = useMemo(() => getPanelDefinition(panel), [panel]);

  return (
    <header className="sticky top-0 z-20 flex h-20 items-center justify-between border-b border-border/50 bg-background/75 px-6 backdrop-blur-xl">
      <div className="flex items-center gap-4">
        {onToggleSidebar && (
          <button
            type="button"
            onClick={onToggleSidebar}
            className="mr-1 inline-flex h-10 w-10 items-center justify-center rounded-full border border-border/60 bg-surface text-muted-foreground shadow-sm transition hover:border-accent/60 hover:text-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 lg:hidden"
            aria-label="Toggle sidebar"
          >
            <Menu className="h-5 w-5" aria-hidden />
          </button>
        )}
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-semibold text-foreground">{definition.label}</h1>
            {typeof memoryCount === 'number' && memoryCount > 0 && (
              <span className="inline-flex items-center rounded-full border border-accent/30 bg-accent/10 px-3 py-1 text-xs font-medium text-accent shadow-inner transition">
                Memory: {memoryCount}
              </span>
            )}
          </div>
          <p className="mt-1 text-sm text-muted-foreground">{definition.description}</p>
        </div>
      </div>
      <div className="flex items-center gap-3">{rightSlot}</div>
    </header>
  );
}
