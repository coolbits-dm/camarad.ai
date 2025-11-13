import type { PlanConfig, PlanId } from '@/lib/types/billing';

export const PLANS: PlanConfig[] = [
  {
    id: 'personal',
    name: 'Personal',
    pricePerMonth: 12,
    description: 'For individual builders and creators.',
    trialDays: 15,
    maxWorkspaces: 3,
    maxAgentsPerUser: 5,
    monthlyCbT: 10_000,
    maxTeamMembers: 1,
    features: [
      'Up to 3 workspaces',
      '5 AI agents included',
      '10,000 cbT per month',
      'Custom agent names',
      'Personal use only',
    ],
  },
  {
    id: 'business',
    name: 'Business',
    pricePerMonth: 49,
    description: 'For teams automating their operations.',
    trialDays: 15,
    maxWorkspaces: 10,
    maxAgentsPerUser: 10,
    monthlyCbT: 40_000,
    maxTeamMembers: 5,
    features: [
      'Up to 10 workspaces',
      '10 AI agents with org roles',
      '40,000 cbT per month',
      'Team access (up to 5 members)',
      'Business integrations',
      'Basic permissions',
    ],
  },
  {
    id: 'agency',
    name: 'Agency',
    pricePerMonth: 149,
    description: 'For agencies managing multiple clients.',
    trialDays: 15,
    maxWorkspaces: 'unlimited',
    maxAgentsPerUser: 20,
    monthlyCbT: 150_000,
    maxTeamMembers: 20,
    features: [
      'Unlimited client workspaces',
      '20 AI agents with marketing roles',
      '150,000 cbT per month',
      'Client workspaces and reporting',
      'Advanced permissions',
      'White-label options',
    ],
  },
  {
    id: 'custom',
    name: 'Custom',
    pricePerMonth: 'contact',
    description: 'Enterprise deployments and on-prem.',
    trialDays: 15,
    maxWorkspaces: 'unlimited',
    maxAgentsPerUser: 'unlimited',
    monthlyCbT: 'pooled',
    maxTeamMembers: 'unlimited',
    features: [
      'Unlimited workspaces and agents',
      'Pooled cbT allocation',
      'Custom integrations',
      'SLA and dedicated support',
      'On-premise or VPC option',
    ],
  },
];

export function getPlan(id: PlanId): PlanConfig {
  const plan = PLANS.find((p) => p.id === id);
  if (!plan) {
    throw new Error(`Unknown plan: ${id}`);
  }
  return plan;
}
