# M16 — Workspace Sharing & Collaboration

**Status**: 🔴 Not Started  
**Priority**: P1 (Important)  
**Estimated Effort**: 4-5 days  
**Dependencies**: M3 (Workspaces), M10 (RBAC)

## Goal

Enable workspace invitations, team member management, and collaborative agent usage.

## Database Schema

```sql
CREATE TABLE workspace_invitations (
  id UUID PRIMARY KEY,
  workspace_id UUID NOT NULL REFERENCES workspaces(id),
  invited_by UUID NOT NULL REFERENCES users(id),
  email VARCHAR(255) NOT NULL,
  role VARCHAR(20) NOT NULL DEFAULT 'member',
  token VARCHAR(255) UNIQUE NOT NULL,
  expires_at TIMESTAMP NOT NULL,
  accepted_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_invitations_email ON workspace_invitations(email);
```

## Invitation Flow

1. Owner/Admin sends invitation via email
2. Recipient receives email with invite link
3. Recipient clicks link → `/accept-invite?token=...`
4. If not logged in, redirect to sign up/login
5. Accept → Add to workspace_members, mark invitation as accepted

## API Endpoints

- `POST /api/workspaces/:id/invitations` - Send invitation
- `GET /api/invitations/:token` - View invitation details
- `POST /api/invitations/:token/accept` - Accept invitation
- `DELETE /api/invitations/:id` - Cancel invitation
- `PATCH /api/workspaces/:id/members/:userId` - Update member role
- `DELETE /api/workspaces/:id/members/:userId` - Remove member

## Key Features

- Email invitations with 7-day expiration
- Role-based permissions (Owner/Admin/Member)
- Member list with role badges
- Remove members (Owner/Admin only)
- Shared agent access within workspace
- Shared cbT pool (Agency/Custom plans)

## Testing

- [ ] Invitations sent successfully
- [ ] Expiration enforced
- [ ] Roles enforced correctly
- [ ] Members can access workspace
- [ ] Shared agents work
- [ ] Token pool shared (Agency)
