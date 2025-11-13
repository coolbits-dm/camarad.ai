import { getPlan } from '@/lib/config/plans';
import type { PlanId } from '@/lib/types/billing';

export function canCreateWorkspace(currentCount: number, planId: PlanId): boolean {
  const plan = getPlan(planId);
  if (plan.maxWorkspaces === 'unlimited') return true;
  return currentCount < plan.maxWorkspaces;
}

export function canCreateAgent(currentCount: number, planId: PlanId): boolean {
  const plan = getPlan(planId);
  if (plan.maxAgentsPerUser === 'unlimited') return true;
  return currentCount < plan.maxAgentsPerUser;
}

export function getMaxWorkspaces(planId: PlanId): number | 'unlimited' {
  const plan = getPlan(planId);
  return plan.maxWorkspaces;
}

export function getMaxAgents(planId: PlanId): number | 'unlimited' {
  const plan = getPlan(planId);
  return plan.maxAgentsPerUser;
}
