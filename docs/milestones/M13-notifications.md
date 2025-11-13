# M13 — Notifications & Events

**Status**: 🔴 Not Started  
**Priority**: P1 (Important)  
**Estimated Effort**: 3-4 days  
**Dependencies**: M2 (User Model)

## Goal

Real-time notification system for subscription events, agent activities, and team updates.

## Database Schema

```sql
CREATE TABLE notifications (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  type VARCHAR(50) NOT NULL,
  title TEXT NOT NULL,
  body TEXT,
  action_url TEXT,
  read_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_notifications_user ON notifications(user_id, created_at DESC);
```

## Notification Types

- `subscription.renewed` - Monthly token grant
- `subscription.expired` - Trial/payment failed
- `agent.limit_reached` - Max agents reached
- `workspace.invitation` - Invited to workspace
- `usage.quota_warning` - 80% tokens used

## API Endpoints

- `GET /api/notifications` - List user notifications
- `PATCH /api/notifications/:id/read` - Mark as read
- `POST /api/notifications/read-all` - Mark all as read
- `DELETE /api/notifications/:id` - Delete notification

## Files

```
/lib/notifications/send.ts
/lib/notifications/types.ts
/pages/api/notifications/index.ts
/components/NotificationBell.tsx
```

## Testing

- [ ] Notifications created on events
- [ ] Real-time updates work
- [ ] Read status persists
- [ ] Notifications paginated
- [ ] Push notifications (optional)
