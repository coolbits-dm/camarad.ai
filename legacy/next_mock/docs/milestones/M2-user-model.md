# M2 — User Core Models

**Status**: 🔴 Not Started  
**Priority**: P0 (Blocker)  
**Estimated Effort**: 2-3 days  
**Dependencies**: M1 (Auth & Identity)

## Goal

Define and implement the complete user data model including profile information, preferences, subscription status, and metadata tracking. This model serves as the foundation for all user-related features.

## Success Criteria

- ✅ Complete User table schema in database
- ✅ Profile CRUD operations functional
- ✅ Preferences stored and retrieved from DB
- ✅ Trial/subscription status tracked
- ✅ Timestamps (createdAt, updatedAt) automatic
- ✅ User serialization compatible with frontend

## Database Schema

```typescript
// User table (extends M1 auth fields)
interface User {
  // Identity (from M1)
  id: string;              // UUID, primary key
  email: string;           // unique, not null
  googleId: string | null; // OAuth provider ID
  
  // Profile
  name: string;            // display name
  avatar: string | null;   // URL to avatar image
  locale: string;          // e.g., 'en', 'ro'
  timezone: string;        // e.g., 'Europe/Bucharest'
  
  // Preferences
  theme: 'light' | 'dark' | 'system';
  accentColor: string;     // e.g., 'violet', 'cyan'
  
  // Subscription (placeholders for M5)
  planId: PlanId | null;           // 'personal', 'business', 'agency', 'custom'
  subscriptionStatus: SubscriptionStatus | null;
  trialEndsAt: Date | null;        // null if not in trial
  subscriptionId: string | null;   // Stripe subscription ID
  
  // Metadata
  createdAt: Date;         // auto
  updatedAt: Date;         // auto
  lastLoginAt: Date | null;
  onboardingCompletedAt: Date | null;
}

type SubscriptionStatus = 
  | 'trialing' 
  | 'active' 
  | 'past_due' 
  | 'canceled' 
  | 'incomplete';
```

## Includes

### 1. Database Migrations
- Extend User table with all fields
- Add indexes on email, googleId
- Set up automatic timestamp triggers
- Add check constraints for enums

### 2. User Repository Layer
```typescript
// /lib/db/repositories/user.ts
interface UserRepository {
  findById(id: string): Promise<User | null>;
  findByEmail(email: string): Promise<User | null>;
  findByGoogleId(googleId: string): Promise<User | null>;
  create(data: CreateUserInput): Promise<User>;
  update(id: string, data: UpdateUserInput): Promise<User>;
  updatePreferences(id: string, prefs: UserPreferences): Promise<User>;
  updateLastLogin(id: string): Promise<void>;
  delete(id: string): Promise<void>;
}
```

### 3. API Endpoints
```typescript
// GET /api/user
// Returns current user profile

// PATCH /api/user
// Updates user profile (name, avatar, locale, timezone)

// PATCH /api/user/preferences
// Updates user preferences (theme, accentColor)

// GET /api/user/subscription
// Returns subscription status (placeholder for M5)
```

### 4. Type Definitions
```typescript
// /lib/types/user.ts
export interface UserProfile {
  id: string;
  email: string;
  name: string;
  avatar: string | null;
  locale: string;
  timezone: string;
}

export interface UserPreferences {
  theme: 'light' | 'dark' | 'system';
  accentColor: string;
}

export interface UserSubscription {
  planId: PlanId | null;
  status: SubscriptionStatus | null;
  trialEndsAt: string | null;
  isTrialing: boolean;
  isActive: boolean;
}
```

### 5. Frontend Hook Updates
```typescript
// /lib/hooks/useUser.ts
export function useUser() {
  const { data: session } = useSession();
  const [user, setUser] = useState<UserProfile | null>(null);
  const [preferences, setPreferences] = useState<UserPreferences | null>(null);
  
  // Fetch from /api/user instead of mock
  // Update profile, preferences
  // Real-time sync with DB
}
```

## Files to Create/Modify

```
/lib/db/schema/
  user.ts                # Complete User model

/lib/db/repositories/
  user.ts                # User CRUD operations

/lib/types/
  user.ts                # User-related types

/lib/hooks/
  useUser.ts             # Update to use real API

/pages/api/user/
  index.ts               # GET, PATCH user profile
  preferences.ts         # PATCH preferences
  subscription.ts        # GET subscription (stub for M5)

/lib/db/migrations/
  002_user_extended.sql  # Migration from M1 basic user
```

## Implementation Steps

### Step 1: Extend Database Schema
1. Create migration adding new fields to User table
2. Add indexes for performance
3. Set up automatic updatedAt trigger
4. Run migration on dev database

### Step 2: Create Repository Layer
1. Implement UserRepository class
2. Add query methods (findById, findByEmail, etc.)
3. Add mutation methods (create, update, delete)
4. Add transaction support for complex updates

### Step 3: Build API Endpoints
1. Create `/api/user` (GET, PATCH)
2. Create `/api/user/preferences` (PATCH)
3. Create `/api/user/subscription` (GET, stub)
4. Add input validation with Zod
5. Add authentication middleware

### Step 4: Update Frontend Hook
1. Remove mock data from `useUser.ts`
2. Fetch user from `/api/user` on mount
3. Implement `updateProfile` mutation
4. Implement `updatePreferences` mutation
5. Add optimistic updates

### Step 5: Update User Profile Modal
1. Connect form to real API
2. Handle loading states
3. Handle error states
4. Show success toast on save
5. Validate input client-side

## Testing Checklist

- [ ] User created via OAuth has all required fields
- [ ] Profile update persists to database
- [ ] Preferences update reflects immediately in UI
- [ ] Timezone changes affect date/time display
- [ ] Locale changes affect UI language (if i18n implemented)
- [ ] Theme preference applies on page load
- [ ] Accent color changes update CSS variables
- [ ] Avatar upload works (if implemented)
- [ ] Concurrent updates don't cause conflicts
- [ ] Deleted user removed from database

## Database Migration

```sql
-- 002_user_extended.sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS locale VARCHAR(10) DEFAULT 'en';
ALTER TABLE users ADD COLUMN IF NOT EXISTS timezone VARCHAR(50) DEFAULT 'UTC';
ALTER TABLE users ADD COLUMN IF NOT EXISTS theme VARCHAR(10) DEFAULT 'system';
ALTER TABLE users ADD COLUMN IF NOT EXISTS accent_color VARCHAR(20) DEFAULT 'violet';
ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_id VARCHAR(20);
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_status VARCHAR(20);
ALTER TABLE users ADD COLUMN IF NOT EXISTS trial_ends_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_id VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarding_completed_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id);
CREATE INDEX IF NOT EXISTS idx_users_plan_id ON users(plan_id);

-- Auto-update updatedAt trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_users_updated_at 
  BEFORE UPDATE ON users
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();
```

## API Response Examples

```typescript
// GET /api/user
{
  "user": {
    "id": "usr_abc123",
    "email": "user@example.com",
    "name": "John Doe",
    "avatar": "https://avatar.url/john.jpg",
    "locale": "en",
    "timezone": "America/New_York"
  },
  "preferences": {
    "theme": "dark",
    "accentColor": "violet"
  },
  "subscription": {
    "planId": "business",
    "status": "trialing",
    "trialEndsAt": "2025-11-28T00:00:00Z",
    "isTrialing": true,
    "isActive": true
  }
}

// PATCH /api/user
{
  "name": "Jane Doe",
  "timezone": "Europe/London"
}

// PATCH /api/user/preferences
{
  "theme": "light",
  "accentColor": "cyan"
}
```

## Validation Rules

```typescript
// Profile validation
const profileSchema = z.object({
  name: z.string().min(1).max(100),
  avatar: z.string().url().nullable(),
  locale: z.enum(['en', 'ro']),
  timezone: z.string().min(1),
});

// Preferences validation
const preferencesSchema = z.object({
  theme: z.enum(['light', 'dark', 'system']),
  accentColor: z.string().min(1).max(20),
});
```

## Output

Upon completion:
- User model fully defined in database
- All user data persisted and queryable
- Profile and preferences editable via UI
- API endpoints secured and validated
- Frontend hooks use real data
- System ready for M3 (Workspaces)
