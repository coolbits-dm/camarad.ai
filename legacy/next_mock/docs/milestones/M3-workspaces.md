# M3 — Workspaces System

**Status**: 🔴 Not Started  
**Priority**: P0 (Blocker)  
**Estimated Effort**: 4-5 days  
**Dependencies**: M2 (User Core Models)

## Goal

Implement multi-workspace support allowing users to create and manage multiple isolated workspaces, with ownership rules and plan-based limits.

## Database Schema

```typescript
interface Workspace {
  id: string;              // UUID
  name: string;
  type: WorkspaceType;     // 'personal' | 'business' | 'agency' | 'developer'
  ownerId: string;         // FK to users
  isActive: boolean;
  createdAt: Date;
  updatedAt: Date;
}

interface WorkspaceMember {
  id: string;
  workspaceId: string;     // FK to workspaces
  userId: string;          // FK to users
  role: MemberRole;        // 'owner' | 'admin' | 'member'
  joinedAt: Date;
}
```

## API Endpoints

- `GET /api/workspaces` - List user's workspaces
- `POST /api/workspaces` - Create new workspace (check limits)
- `GET /api/workspaces/:id` - Get workspace details
- `PATCH /api/workspaces/:id` - Update workspace
- `DELETE /api/workspaces/:id` - Delete workspace (owner only)
- `GET /api/workspaces/:id/members` - List members (M10+)

## Key Features

- Workspace limit enforcement based on plan
- Default workspace redirect after login
- Workspace switching in UI header
- Isolated data per workspace
- Owner transfer capability
- Workspace deletion with cascade

## Files

```
/lib/db/schema/workspace.ts
/lib/db/repositories/workspace.ts
/pages/api/workspaces/
/lib/hooks/useWorkspace.ts
/components/workspace/WorkspaceSwitcher.tsx
```

## Testing

- [ ] User can create workspace up to plan limit
- [ ] Exceeding limit returns error
- [ ] Workspace deletion cascades to agents
- [ ] Owner can transfer ownership
- [ ] Non-owner cannot delete workspace
