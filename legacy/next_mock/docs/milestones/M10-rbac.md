# M10 — Role-Based Access Control

**Status**: 🔴 Not Started  
**Priority**: P2 (Medium)  
**Estimated Effort**: 3-4 days  
**Dependencies**: M3 (Workspaces)

## Goal

Implement workspace roles and permissions system.

## Roles

- **Owner**: Full control, billing access, can delete workspace
- **Admin**: Manage members, agents, settings
- **Member**: Use agents, view workspace

## Permissions Matrix

| Action | Owner | Admin | Member |
|--------|-------|-------|--------|
| View workspace | ✅ | ✅ | ✅ |
| Use agents | ✅ | ✅ | ✅ |
| Create agents | ✅ | ✅ | ❌ |
| Delete agents | ✅ | ✅ | ❌ |
| Manage members | ✅ | ✅ | ❌ |
| Billing | ✅ | ❌ | ❌ |
| Delete workspace | ✅ | ❌ | ❌ |

## Files

```
/lib/permissions/checker.ts
/lib/middleware/checkWorkspaceAccess.ts
```

## Testing

- [ ] Member cannot delete agents
- [ ] Admin can manage members
- [ ] Only owner accesses billing
- [ ] Permission checks on all endpoints
