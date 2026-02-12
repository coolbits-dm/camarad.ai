# M9 — Settings & Preferences DB Sync

**Status**: 🔴 Not Started  
**Priority**: P2 (Medium)  
**Estimated Effort**: 2 days  
**Dependencies**: M2 (User Core Models)

## Goal

Remove localStorage-based preferences and sync all settings with database.

## Settings to Migrate

- Theme (light/dark/system)
- Accent color
- Timezone
- Locale
- Notification preferences
- Display preferences

## Implementation

- Remove all `localStorage.setItem()` calls
- Fetch preferences from `/api/user` on load
- Persist changes via `/api/user/preferences`
- Optimistic UI updates
- Sync across devices/tabs

## Files

```
/lib/hooks/usePreferences.ts
/pages/api/user/preferences.ts
/components/settings/
```

## Testing

- [ ] Theme persists across devices
- [ ] Changes reflect immediately
- [ ] No localStorage remnants
- [ ] Preferences load on SSR
