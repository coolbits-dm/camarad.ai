# M12 — AI Runtime Integration (cbLM Relay)

**Status**: 🔴 Not Started  
**Priority**: P0 (Blocker)  
**Estimated Effort**: 5-7 days  
**Dependencies**: M4 (Agents), M6 (cbT Ledger), M7 (Usage Metering)

## Goal

Integrate cbLM relay to make agents functional, with token charging and usage tracking.

## Architecture

```
User → Frontend → Backend API → cbLM Relay → OpenAI/Anthropic
                       ↓
                  Usage Tracking
                       ↓
                  Token Deduction
```

## API Endpoints

- `POST /api/agents/:id/chat` - Send message to agent
- `POST /api/agents/:id/stream` - Streaming chat
- `GET /api/agents/:id/history` - Conversation history

## Key Features

- Agent invocation via cbLM relay
- Token consumption from ledger
- Real-time usage metering
- Error handling and retries
- Streaming responses
- Conversation history storage
- Rate limiting per agent

## Files

```
/lib/cblm/client.ts
/lib/cblm/streaming.ts
/pages/api/agents/[id]/chat.ts
/pages/api/agents/[id]/stream.ts
```

## Testing

- [ ] Agent responds to messages
- [ ] Tokens deducted correctly
- [ ] Usage recorded in DB
- [ ] Streaming works
- [ ] Errors handled gracefully
- [ ] Insufficient tokens blocked
