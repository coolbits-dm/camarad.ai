# M5 — Billing & Stripe

**Status**: 🔴 Not Started  
**Priority**: P1 (High)  
**Estimated Effort**: 5-7 days  
**Dependencies**: M2 (User Core Models)

## Goal

Integrate Stripe for payment processing, subscription management, and 15-day trial activation.

## Stripe Integration

```typescript
interface StripeCustomer {
  userId: string;
  stripeCustomerId: string;
  createdAt: Date;
}
```

## API Endpoints

- `POST /api/billing/checkout` - Create checkout session
- `POST /api/billing/portal` - Get billing portal link
- `POST /api/billing/webhook` - Stripe webhook handler
- `GET /api/billing/subscription` - Current subscription status

## Webhook Events

- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.payment_succeeded`
- `invoice.payment_failed`

## Key Features

- Create Stripe customer on signup
- 15-day trial with card required
- Checkout session for plan upgrades
- Billing portal for plan management
- Webhook sync to update user.subscriptionStatus
- Prorated plan changes
- Subscription cancellation

## Files

```
/lib/stripe/client.ts
/lib/stripe/webhooks.ts
/pages/api/billing/
/components/billing/
```

## Testing

- [ ] Checkout creates Stripe customer
- [ ] Trial starts immediately with card
- [ ] Trial ends after 15 days → charged
- [ ] Upgrade/downgrade prorated correctly
- [ ] Cancellation processes successfully
- [ ] Webhooks sync DB state
