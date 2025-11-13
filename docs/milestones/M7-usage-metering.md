# M7 — Usage Metering

**Status**: 🔴 Not Started  
**Priority**: P1 (High)  
**Estimated Effort**: 3-4 days  
**Dependencies**: M6 (cbT Ledger), M4 (Agents)

## Goal

Track all AI usage (calls, tokens, cost) for analytics, billing, and quota enforcement.

## Database Schema

```typescript
interface UsageEvent {
  id: string;
  userId: string;
  workspaceId: string;
  agentId: string;
  requestId: string;
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  cbtCost: number;          // Tokens consumed from ledger
  model: string;            // e.g., 'gpt-4'
  provider: string;         // e.g., 'openai'
  status: 'success' | 'error';
  errorMessage: string | null;
  createdAt: Date;
}
```

## API Endpoints

- `GET /api/usage` - Usage history
- `GET /api/usage/stats` - Aggregated statistics
- `POST /api/usage/record` - Record usage (internal)

## Key Features

- Real-time usage tracking
- Token cost calculation
- Daily/monthly aggregations
- Usage graphs in dashboard
- Export usage reports
- Quota warnings

## Files

```
/lib/db/schema/usage.ts
/lib/db/repositories/usage.ts
/pages/api/usage/
/components/usage/UsageChart.tsx
```

## Testing

- [ ] AI call creates usage event
- [ ] Tokens counted accurately
- [ ] Cost synced with ledger
- [ ] Stats API returns correct totals
- [ ] Usage graphs render correctly
