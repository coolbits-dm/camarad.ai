# M11 — API Gateway Hardening

**Status**: 🔴 Not Started  
**Priority**: P1 (High)  
**Estimated Effort**: 3-4 days  
**Dependencies**: M1 (Auth)

## Goal

Secure all API endpoints with validation, rate limiting, and proper error handling.

## Security Layers

1. **Authentication** - All endpoints require valid session
2. **Input Validation** - Zod schemas for all inputs
3. **Rate Limiting** - Per-user and per-IP limits
4. **Workspace Isolation** - Users only access own workspaces
5. **CORS** - Proper origin restrictions
6. **CSRF Protection** - Token validation

## Implementation

```typescript
// Rate limiting
- 100 requests/minute per user
- 1000 requests/hour per IP
- Special limits for AI endpoints

// Validation
- All inputs validated with Zod
- Type-safe request/response
- Clear error messages

// Error handling
- Consistent error format
- Proper HTTP status codes
- No sensitive data leakage
```

## Files

```
/lib/middleware/rateLimit.ts
/lib/middleware/validate.ts
/lib/middleware/errorHandler.ts
```

## Testing

- [ ] Invalid input rejected
- [ ] Rate limit enforced
- [ ] Unauthenticated requests blocked
- [ ] Cross-workspace access denied
