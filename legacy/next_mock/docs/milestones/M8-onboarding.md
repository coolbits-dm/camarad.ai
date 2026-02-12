# M8 — Onboarding Integration

**Status**: 🔴 Not Started  
**Priority**: P1 (High)  
**Estimated Effort**: 2-3 days  
**Dependencies**: M4 (Agents), M5 (Billing)

## Goal

Connect onboarding flow to real database operations, creating workspaces, agents, and activating trials.

## Onboarding Flow

1. User completes OAuth (M1)
2. Plan selection → store `planId`
3. Workspace creation → DB insert
4. Agent selection → bulk agent creation
5. Preferences → update user record
6. Stripe checkout → activate trial
7. Redirect to workspace

## API Implementation

```typescript
// POST /api/onboarding/complete
interface OnboardingPayload {
  planId: PlanId;
  workspace: {
    name: string;
    type: WorkspaceType;
  };
  selectedAgentPresetIds: string[];
  preferences: UserPreferences;
}

// Response
interface OnboardingResponse {
  success: boolean;
  userId: string;
  workspaceId: string;
  agentIds: string[];
  trialEndsAt: string;
  checkoutUrl: string;      // Stripe checkout URL
}
```

## Key Features

- Atomic transaction for all DB operations
- Stripe checkout session creation
- Trial activation on card add
- Default workspace selection
- Agent provisioning from presets
- Preferences sync to DB
- Onboarding completion flag

## Files

```
/pages/api/onboarding/complete.ts (update from mock)
/lib/onboarding/processor.ts
```

## Testing

- [ ] Onboarding creates workspace in DB
- [ ] Agents created from selected presets
- [ ] Stripe checkout URL returned
- [ ] Trial starts after card added
- [ ] Preferences saved to user record
- [ ] User redirected to new workspace
