# Camarad Backend

Real backend for Camarad.ai with authentication, user management, and API endpoints.

## Tech Stack

- **Framework**: Fastify
- **Database**: PostgreSQL + Prisma ORM
- **Auth**: JWT + HTTP-only cookies + Argon2id
- **Language**: TypeScript

## Setup

### 1. Install Dependencies

```bash
cd backend
npm install
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your values
```

Required variables:
- `DATABASE_URL` - PostgreSQL connection string
- `JWT_SECRET` - Secret for JWT signing (min 32 chars)
- `GOOGLE_CLIENT_ID` - Google OAuth client ID
- `GOOGLE_CLIENT_SECRET` - Google OAuth client secret

### 3. Database Setup

```bash
# Generate Prisma client
npx prisma generate

# Run migrations
npx prisma migrate dev

# (Optional) Open Prisma Studio
npx prisma studio
```

### 4. Run Development Server

```bash
npm run dev
```

Server will start on `http://localhost:3001`

## API Endpoints

### Authentication

- `POST /auth/register` - Register new user
- `POST /auth/login` - Login with email/password
- `POST /auth/logout` - Logout (invalidate session)
- `GET /auth/session` - Get current session

### User Management

- `GET /user/me` - Get current user profile
- `PATCH /user/me` - Update user profile

### Health Check

- `GET /health` - Server health status

## Project Structure

```
backend/
├── src/
│   ├── auth/           # Authentication logic
│   ├── users/          # User management
│   ├── middleware/     # Auth guards, etc.
│   ├── config/         # Environment & logging
│   ├── db/             # Database client
│   ├── types/          # TypeScript types
│   └── server.ts       # Main entry point
├── prisma/
│   └── schema.prisma   # Database schema
└── package.json
```

## Development

```bash
# Run dev server with hot reload
npm run dev

# Build for production
npm run build

# Start production server
npm start

# Run tests
npm test

# Lint code
npm run lint
```

## Production Deployment

### 1. Build

```bash
npm run build
```

### 2. Set Production Environment

```env
NODE_ENV=production
PORT=8080
DATABASE_URL=postgresql://user:pass@host:5432/camarad_prod
COOKIE_SECURE=true
COOKIE_SAME_SITE=strict
```

### 3. Run with PM2

```bash
pm2 start dist/server.js --name camarad-api
pm2 save
```

### 4. Nginx Reverse Proxy

```nginx
server {
    listen 443 ssl;
    server_name api.camarad.ai;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Security

- Passwords hashed with Argon2id (OWASP recommended)
- JWT tokens in HTTP-only cookies
- CORS configured
- Rate limiting (TODO)
- Input validation with Zod
- SQL injection protected (Prisma ORM)

## Milestones

✅ **M1 - Authentication & Users**
- Email/password registration
- Login/logout
- Session management
- JWT authentication
- User profile management

🔜 **M2 - Workspaces** (Next)
🔜 **M3 - Agents**
🔜 **M4 - Billing & cbT Ledger**

## License

MIT
