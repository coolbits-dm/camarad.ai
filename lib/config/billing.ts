import type { PlanId } from '@/lib/types/billing';

export interface BillingInfo {
  planId: PlanId;
  trialEndsAt: Date | null;
  subscriptionStatus: 'trialing' | 'active' | 'past_due' | 'canceled' | 'incomplete';
  paymentMethodAdded: boolean;
  nextBillingDate: Date | null;
}

export interface PaymentMethod {
  id: string;
  brand: string;
  last4: string;
  expiryMonth: number;
  expiryYear: number;
}

export interface SubscriptionDetails {
  id: string;
  planId: PlanId;
  status: 'trialing' | 'active' | 'past_due' | 'canceled';
  currentPeriodStart: Date;
  currentPeriodEnd: Date;
  trialEnd: Date | null;
  cancelAtPeriodEnd: boolean;
}

// Placeholder functions for Stripe integration
export async function addPaymentMethod(token: string): Promise<PaymentMethod> {
  // TODO: Integrate with Stripe
  throw new Error('Stripe integration pending');
}

export async function createSubscription(planId: PlanId): Promise<SubscriptionDetails> {
  // TODO: Integrate with Stripe
  throw new Error('Stripe integration pending');
}

export async function cancelSubscription(subscriptionId: string): Promise<void> {
  // TODO: Integrate with Stripe
  throw new Error('Stripe integration pending');
}
