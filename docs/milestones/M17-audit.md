# M17 — Audit Logs

**Status**: 🔴 Not Started  
**Priority**: P2 (Nice to Have)  
**Estimated Effort**: 2-3 days  
**Dependencies**: M3 (Workspaces), M4 (Agents)

## Goal

Comprehensive audit logging for compliance, security, and debugging.

## Database Schema

```sql
CREATE TABLE audit_logs (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id),
  workspace_id UUID REFERENCES workspaces(id),
  action VARCHAR(100) NOT NULL,
  resource_type VARCHAR(50) NOT NULL,
  resource_id UUID,
  metadata JSONB,
  ip_address INET,
  user_agent TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_audit_user ON audit_logs(user_id, created_at DESC);
CREATE INDEX idx_audit_workspace ON audit_logs(workspace_id, created_at DESC);
CREATE INDEX idx_audit_action ON audit_logs(action, created_at DESC);
```

## Logged Actions

- `user.login` / `user.logout`
- `workspace.created` / `workspace.deleted`
- `agent.created` / `agent.deleted`
- `member.invited` / `member.removed`
- `subscription.created` / `subscription.cancelled`
- `settings.updated`
- `api.rate_limited`

## API Endpoints

- `GET /api/audit-logs` - List audit logs (admin only)
- `GET /api/workspaces/:id/audit-logs` - Workspace logs (owner/admin)

## Key Features

- Immutable append-only logs
- IP address and user agent tracking
- Metadata stored as JSONB
- Retention policy (90 days)
- Export to CSV

## Testing

- [ ] All major actions logged
- [ ] Metadata captured correctly
- [ ] Logs accessible to authorized users
- [ ] Export works
- [ ] Retention policy enforced
