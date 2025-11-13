import type { AgentPreset } from '@/lib/types/agent';
import { PERSONAL_AGENT_PRESETS } from './personal';
import { BUSINESS_AGENT_PRESETS } from './business';
import { AGENCY_AGENT_PRESETS } from './agency';
import { DEVELOPER_AGENT_PRESETS } from './developer';

export const ALL_AGENT_PRESETS: AgentPreset[] = [
  ...PERSONAL_AGENT_PRESETS,
  ...BUSINESS_AGENT_PRESETS,
  ...AGENCY_AGENT_PRESETS,
  ...DEVELOPER_AGENT_PRESETS,
];

export function getAgentPreset(id: string): AgentPreset | undefined {
  return ALL_AGENT_PRESETS.find((preset) => preset.id === id);
}

export { PERSONAL_AGENT_PRESETS, BUSINESS_AGENT_PRESETS, AGENCY_AGENT_PRESETS, DEVELOPER_AGENT_PRESETS };
