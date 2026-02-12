# Camarad Development Milestones

This directory contains the complete development roadmap for Camarad, organized into 19 sequential milestones. Each milestone represents a cohesive set of features that can be developed, tested, and deployed independently.

## Milestone Overview

### Phase 1: Foundation (M1-M4)
- **M1** — [Auth & Identity](./M1-auth.md) - Real OAuth implementation, no mocks
- **M2** — [User Core Models](./M2-user-model.md) - Complete user data structure
- **M3** — [Workspaces System](./M3-workspaces.md) - Multi-workspace support per user
- **M4** — [Agent Provisioning](./M4-agents.md) - Real agent instantiation from presets

### Phase 2: Monetization (M5-M7)
- **M5** — [Billing & Stripe](./M5-billing.md) - Payment processing, trials, subscriptions
- **M6** — [cbT Ledger](./M6-cbt-ledger.md) - Token accounting and balance tracking
- **M7** — [Usage Metering](./M7-usage-metering.md) - AI call tracking and cost attribution

### Phase 3: Integration (M8-M9)
- **M8** — [Onboarding Integration](./M8-onboarding.md) - Real onboarding flow creating DB objects
- **M9** — [Settings & Preferences DB Sync](./M9-settings.md) - Persistent user preferences

### Phase 4: Security & Control (M10-M11)
- **M10** — [Role-Based Access Control](./M10-rbac.md) - Workspace permissions and roles
- **M11** — [API Gateway Hardening](./M11-api-security.md) - Security, validation, rate limiting

### Phase 5: Runtime (M12-M13)
- **M12** — [AI Runtime Integration](./M12-ai-runtime.md) - cbLM relay integration
- **M13** — [Notifications & Events](./M13-notifications.md) - Real-time event system

### Phase 6: Operations (M14-M15)
- **M14** — [Production Deployment & Observability](./M14-ops.md) - Cloud deployment, monitoring
- **M15** — [Safety, Limits & Abuse Prevention](./M15-safety.md) - AI safety guardrails

### Phase 7: Advanced Features (M16-M18)
- **M16** — [Workspace Sharing](./M16-sharing.md) - Collaboration and invitations
- **M17** — [Audit Logs](./M17-audit.md) - Complete action tracking
- **M18** — [Custom Agents & Prompt Editor](./M18-custom-agents.md) - User-created agents

### Phase 8: Ecosystem (M19)
- **M19** — [Marketplace Prep](./M19-marketplace.md) - Public templates and agent sharing

## Current Status

**Active Development**: Foundation Phase (M1-M4)

**Completed**:
- UI scaffolding and design system
- Type system and configuration structure
- Agent presets (40 total across 4 domains)
- Plan configuration with real limits
- Mock authentication and onboarding flow

**Next Up**: M1 - Real OAuth implementation

## Development Principles

1. **No Mocks in Production** - Each milestone removes mock implementations
2. **Database First** - All state persisted in PostgreSQL
3. **Type Safety** - Full TypeScript coverage
4. **Security by Default** - Auth required, input validated, rate limited
5. **Incremental** - Each milestone deployable independently
6. **Observable** - Logging, tracing, metrics from day one

## File Structure

Each milestone document includes:
- **Goal** - What this milestone achieves
- **Includes** - Detailed feature list
- **Files** - Paths to implementation files
- **Output** - Success criteria
- **Dependencies** - Required prior milestones
- **Testing** - Verification steps
- **Rollback** - Revert strategy if needed
