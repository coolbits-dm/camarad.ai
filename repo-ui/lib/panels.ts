import type { LucideIcon } from 'lucide-react';
import { Briefcase, Building2, Code2, UserCircle2 } from 'lucide-react';

export type PanelKey = 'personal' | 'business' | 'agency' | 'developer';

export interface PanelDefinition {
  key: PanelKey;
  label: string;
  description: string;
  icon: LucideIcon;
}

export const PANEL_DEFINITIONS = [
  {
    key: 'personal',
    label: 'Personal',
    description: 'Your individual workspace and personal memories.',
    icon: UserCircle2,
  },
  {
    key: 'business',
    label: 'Business',
    description: 'Operational insights for business workflows and teams.',
    icon: Briefcase,
  },
  {
    key: 'agency',
    label: 'Agency',
    description: 'Agency orchestrations, clients, and queue snapshots.',
    icon: Building2,
  },
  {
    key: 'developer',
    label: 'Developer',
    description: 'Developer diagnostics, connectors, and integration hooks.',
    icon: Code2,
  },
] satisfies PanelDefinition[];

export const DEFAULT_PANEL: PanelKey = 'personal';

export function isPanelKey(value: string | undefined): value is PanelKey {
  return PANEL_DEFINITIONS.some((panel) => panel.key === value);
}

export function getPanelDefinition(panel: PanelKey): PanelDefinition {
  const match = PANEL_DEFINITIONS.find((definition) => definition.key === panel);
  if (!match) {
    throw new Error(`Unknown panel: ${panel}`);
  }
  return match;
}
