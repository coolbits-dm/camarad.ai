# M6 — cbT Ledger

**Status**: 🔴 Not Started  
**Priority**: P1 (High)  
**Estimated Effort**: 3-4 days  
**Dependencies**: M5 (Billing)

## Goal

Implement token ledger system to track cbT (CoolBits Token) allocation, consumption, and balance.

## Database Schema

```typescript
interface LedgerEntry {
  id: string;
  userId: string;
  workspaceId: string | null;
  type: 'grant' | 'consume' | 'refund';
  delta: number;           // +positive for grant, -negative for consume
  balance: number;         // Running balance after this entry
  reason: string;          // 'monthly_grant', 'ai_call', 'refund'
  metadata: object;        // { agentId, requestId, etc. }
  createdAt: Date;
}
```

## API Endpoints

- `GET /api/ledger` - User's ledger history
- `GET /api/ledger/balance` - Current token balance
- `POST /api/ledger/grant` - Grant tokens (admin/system)
- `POST /api/ledger/consume` - Consume tokens (internal)

## Key Features

- Monthly token grants on subscription renewal
- Token consumption on AI calls (M12)
- Refunds for failed calls
- Balance calculation queries
- Ledger immutability (append-only)
- Per-workspace allocation tracking

## Files

```
/lib/db/schema/ledger.ts
/lib/db/repositories/ledger.ts
/pages/api/ledger/
/lib/hooks/useTokenBalance.ts
```

## Testing

- [ ] Monthly grant creates ledger entry
- [ ] AI call consumes tokens correctly
- [ ] Balance reflects sum of all deltas
- [ ] Cannot consume more than available
- [ ] Refund adds tokens back
