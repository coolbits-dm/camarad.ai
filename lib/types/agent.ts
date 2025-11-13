export type AgentDomain = 'lifestyle' | 'business' | 'agency' | 'developer';

export interface AgentPreset {
  id: string;
  domain: AgentDomain;
  name: string;
  description: string;
  icon: string;
  defaultRolePrompt: string;
}

export interface UserAgent {
  id: string;
  presetId: string;
  workspaceId: string;
  customName?: string;
  isActive: boolean;
}
