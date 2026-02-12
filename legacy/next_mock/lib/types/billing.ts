export type PlanId = 'personal' | 'business' | 'agency' | 'custom';

export interface PlanLimits {
  maxWorkspaces: number | 'unlimited';
  maxAgentsPerUser: number | 'unlimited';
  monthlyCbT: number | 'pooled';
  maxTeamMembers: number | 'unlimited';
}

export interface PlanConfig extends PlanLimits {
  id: PlanId;
  name: string;
  pricePerMonth: number | 'contact';
  description: string;
  trialDays: number;
  features: string[];
}
