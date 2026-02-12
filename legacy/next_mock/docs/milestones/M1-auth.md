# M1 — Auth & Identity (OAuth Real)

**Status**: 🔴 Not Started  
**Priority**: P0 (Blocker)  
**Estimated Effort**: 3-5 days  
**Dependencies**: None

## Goal

Replace mock authentication with a real OAuth implementation. Users must be able to sign in with Google (and optionally email magic links), with sessions persisted server-side and user records created in the database.

## Success Criteria

- ✅ Google OAuth functional (sign in, sign up)
- ✅ User record created in DB on first login
- ✅ Server-side session management
- ✅ Protected API routes require authentication
- ✅ SSR-compatible session provider
- ✅ JWT signing keys configured
- ✅ Logout clears session completely

## Includes

### 1. OAuth Provider Setup
- Google Cloud Console project configuration
- OAuth 2.0 client ID and secret
- Authorized redirect URIs configured
- Scopes: email, profile, openid

### 2. NextAuth.js Integration
- Install `next-auth` package
- Configure Google provider
- Session strategy: JWT or database sessions
- JWT secret key generation
- Callback URLs setup

### 3. Database Schema
```typescript
// User table
interface User {
  id: string;              // UUID
  email: string;           // unique
  name: string | null;
  avatar: string | null;
  googleId: string | null; // OAuth provider ID
  createdAt: Date;
  updatedAt: Date;
}
```

### 4. Session Management
- Session provider wrapping app
- `useSession()` hook for client components
- `getServerSession()` for API routes and SSR
- Session expiry: 30 days
- Refresh token handling

### 5. Protected Routes
- Middleware to check authentication
- Redirect unauthenticated users to `/login`
- API routes return 401 if no session
- Allow public routes: `/`, `/login`, `/register`

### 6. Email Magic Link (Optional)
- Email provider configuration (SendGrid/Resend)
- Magic link generation
- Link expiry: 15 minutes
- Rate limiting on email sends

## Files to Create/Modify

```
/lib/auth/
  config.ts              # NextAuth configuration
  session.ts             # Session utilities (replaces mock)
  
/pages/api/auth/
  [...nextauth].ts       # NextAuth API routes
  
/lib/db/schema/
  user.ts                # User model schema
  
/lib/db/
  client.ts              # Database client setup
  
/pages/
  login.tsx              # Update with real OAuth
  register.tsx           # Update with real OAuth
  
/middleware.ts           # Update with real auth checks

/.env.local
  GOOGLE_CLIENT_ID=
  GOOGLE_CLIENT_SECRET=
  NEXTAUTH_SECRET=
  NEXTAUTH_URL=
  DATABASE_URL=
```

## Implementation Steps

### Step 1: Database Setup
1. Create PostgreSQL database
2. Install Prisma or Drizzle ORM
3. Define User schema
4. Run migrations
5. Test DB connection

### Step 2: NextAuth Configuration
1. Install `next-auth`
2. Create `/pages/api/auth/[...nextauth].ts`
3. Configure Google provider
4. Set up callbacks (jwt, session)
5. Configure session strategy

### Step 3: Google OAuth Setup
1. Create project in Google Cloud Console
2. Enable Google+ API
3. Create OAuth 2.0 credentials
4. Add authorized redirect URI: `https://camarad.ai/api/auth/callback/google`
5. Copy client ID and secret to `.env.local`

### Step 4: Session Provider
1. Wrap `_app.tsx` with `SessionProvider`
2. Update `useSession()` calls to use real hook
3. Remove mock session utilities
4. Test SSR with `getServerSession()`

### Step 5: Route Protection
1. Update middleware to check real sessions
2. Protect `/p/*` routes
3. Protect `/api/*` routes (except auth endpoints)
4. Redirect to `/login` with `callbackUrl`

### Step 6: User Creation Flow
1. On first OAuth login, create User record
2. Store OAuth provider ID (googleId)
3. Set default preferences
4. Redirect to onboarding if new user
5. Redirect to dashboard if returning user

## Testing Checklist

- [ ] Google OAuth sign-in creates user in DB
- [ ] User record has correct email, name, avatar
- [ ] Session persists across page refreshes
- [ ] Logout clears session completely
- [ ] Protected routes redirect to login
- [ ] API routes return 401 without session
- [ ] SSR pages can access session
- [ ] Session expires after 30 days
- [ ] Multiple tabs stay synchronized
- [ ] Works in incognito mode

## Environment Variables

```bash
# Database
DATABASE_URL="postgresql://user:password@localhost:5432/camarad"

# NextAuth
NEXTAUTH_URL="https://camarad.ai"
NEXTAUTH_SECRET="<generate-random-secret>"

# Google OAuth
GOOGLE_CLIENT_ID="<from-google-console>"
GOOGLE_CLIENT_SECRET="<from-google-console>"

# Email (optional)
EMAIL_SERVER="smtp://user:pass@smtp.sendgrid.net:587"
EMAIL_FROM="noreply@camarad.ai"
```

## Security Considerations

- Store `NEXTAUTH_SECRET` securely (32+ random characters)
- Use HTTPS in production
- Set `secure: true` for cookies in production
- Implement CSRF protection (built into NextAuth)
- Rate limit login attempts
- Log all authentication events
- Validate OAuth tokens server-side

## Rollback Plan

If issues arise:
1. Revert to mock authentication
2. Disable OAuth provider in NextAuth config
3. Clear user sessions from database
4. Restore previous middleware logic

## Dependencies

**Required Packages**:
```json
{
  "next-auth": "^4.24.0",
  "@prisma/client": "^5.0.0",
  "prisma": "^5.0.0"
}
```

**External Services**:
- PostgreSQL database
- Google OAuth 2.0 credentials
- Email provider (optional)

## Migration from Mock

1. ✅ Identify all uses of mock `lib/auth/session.ts`
2. ✅ Replace with NextAuth `useSession()` hook
3. ✅ Update API routes to use `getServerSession()`
4. ✅ Remove localStorage-based session logic
5. ✅ Update login/register pages with OAuth buttons
6. ✅ Test complete auth flow end-to-end

## Output

Upon completion:
- Real users can sign in with Google
- User data persisted in PostgreSQL
- Sessions managed server-side
- All protected routes require authentication
- No mock authentication code remains
- System ready for M2 (User Core Models)
