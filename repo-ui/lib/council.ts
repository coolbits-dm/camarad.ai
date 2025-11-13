import type { CouncilMember } from '@/types/chat';
import type { PanelKey } from '@/lib/panels';

export const COUNCIL_ROSTER: CouncilMember[] = [
  {
    id: 'personal-avery',
    name: 'Avery Cole',
    handle: '@avery',
    specialty: 'Personal insights',
    panel: 'personal',
  },
  {
    id: 'personal-jo',
    name: 'Jordan Ruiz',
    handle: '@jo',
    specialty: 'Executive updates',
    panel: 'personal',
  },
  {
    id: 'business-sloane',
    name: 'Sloane Wells',
    handle: '@sloane',
    specialty: 'Revenue ops',
    panel: 'business',
  },
  {
    id: 'business-mira',
    name: 'Mira Patel',
    handle: '@mira',
    specialty: 'Lifecycle marketing',
    panel: 'business',
  },
  {
    id: 'agency-rory',
    name: 'Rory Blake',
    handle: '@rory',
    specialty: 'Agency orchestration',
    panel: 'agency',
  },
  {
    id: 'agency-fern',
    name: 'Fern Ibarra',
    handle: '@fern',
    specialty: 'Client success',
    panel: 'agency',
  },
  {
    id: 'developer-ada',
    name: 'Ada Stone',
    handle: '@ada',
    specialty: 'Integrations',
    panel: 'developer',
  },
  {
    id: 'developer-lio',
    name: 'Lio Harper',
    handle: '@lio',
    specialty: 'Platform reliability',
    panel: 'developer',
  },
];

export function getCouncilMembers(panel?: PanelKey) {
  if (!panel) {
    return COUNCIL_ROSTER;
  }
  return COUNCIL_ROSTER.filter((member) => member.panel === panel);
}

export function searchCouncilMembers(query: string, panel?: PanelKey) {
  const normalized = query.trim().toLowerCase();
  const base = panel ? getCouncilMembers(panel) : COUNCIL_ROSTER;
  if (!normalized) return base;
  return base.filter((member) => {
    return (
      member.name.toLowerCase().includes(normalized) ||
      member.handle.toLowerCase().includes(normalized) ||
      (member.specialty?.toLowerCase().includes(normalized) ?? false)
    );
  });
}
