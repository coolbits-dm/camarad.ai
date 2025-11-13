# M4 — Agent Provisioning

**Status**: 🔴 Not Started  
**Priority**: P0 (Blocker)  
**Estimated Effort**: 3-4 days  
**Dependencies**: M3 (Workspaces)

## Goal

Implement real agent provisioning from presets, with database persistence and plan-based limits.

## Database Schema

```typescript
interface Agent {
  id: string;              // UUID
  workspaceId: string;     // FK to workspaces
  presetId: string;        // e.g., 'ceo', 'coach'
  customName: string | null;
  isActive: boolean;
  createdAt: Date;
  updatedAt: Date;
}

interface AgentPreset {
  id: string;
  domain: AgentDomain;
  name: string;
  description: string;
  icon: string;
  defaultRolePrompt: string;
  isPublic: boolean;       // For marketplace (M19)
}
```

## API Endpoints

- `GET /api/workspaces/:id/agents` - List workspace agents
- `POST /api/workspaces/:id/agents` - Create agent (check limits)
- `GET /api/agents/:id` - Get agent details
- `PATCH /api/agents/:id` - Update agent (custom name)
- `DELETE /api/agents/:id` - Delete agent
- `GET /api/agent-presets` - List available presets

## Key Features

- Agent limit enforcement per plan
- Preset selection based on workspace type
- Custom agent naming
- Agent activation/deactivation
- Bulk agent creation during onboarding
- Agent deletion with cleanup

## Files

```
/lib/db/schema/agent.ts
/lib/db/repositories/agent.ts
/pages/api/agents/
/pages/api/workspaces/[id]/agents/
/lib/hooks/useAgents.ts
```

## Testing

- [ ] Agent created from preset
- [ ] Custom name overrides preset name
- [ ] Cannot exceed plan agent limit
- [ ] Agent deletion successful
- [ ] Workspace deletion cascades to agents
