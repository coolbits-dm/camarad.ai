# M15 — Safety, Limits & Abuse Prevention

**Status**: 🔴 Not Started  
**Priority**: P0 (Blocker)  
**Estimated Effort**: 3-5 days  
**Dependencies**: M11 (API Security), M12 (AI Runtime)

## Goal

Implement AI safety guardrails, prompt injection protection, quota enforcement, and abuse detection.

## Safety Layers

1. **Input Validation** - Reject harmful prompts
2. **Prompt Injection Defense** - Prevent system prompt override
3. **Content Filtering** - Block unsafe outputs
4. **Rate Limiting** - Prevent abuse
5. **Quota Enforcement** - Hard stop at 0 tokens
6. **Anomaly Detection** - Flag suspicious usage patterns

## Safety Database

```sql
CREATE TABLE safety_flags (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL,
  agent_id UUID,
  type VARCHAR(50) NOT NULL, -- 'prompt_injection', 'rate_limit', 'quota_exceeded'
  severity VARCHAR(20), -- 'low', 'medium', 'high', 'critical'
  reason TEXT,
  metadata JSONB,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_safety_user ON safety_flags(user_id, created_at DESC);
```

## Prompt Injection Detection

```typescript
const INJECTION_PATTERNS = [
  /ignore (previous|all) instructions/i,
  /disregard (your|the) system prompt/i,
  /you are now/i,
  /new instructions:/i,
];
```

## Rate Limits

- 100 messages/hour per agent (free tier)
- 500 messages/hour (Business/Agency)
- 10 agents active simultaneously per workspace

## Testing

- [ ] Injection attempts blocked
- [ ] Quota enforcement works
- [ ] Rate limits enforced
- [ ] Anomaly alerts fire
- [ ] Flagged users reviewed
