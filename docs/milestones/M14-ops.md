# M14 — Production Deployment & Observability

**Status**: 🔴 Not Started  
**Priority**: P0 (Blocker)  
**Estimated Effort**: 4-6 days  
**Dependencies**: M1-M13 (All previous milestones)

## Goal

Deploy Camarad to production with monitoring, logging, error tracking, and automated backups.

## Infrastructure

- **Hosting**: Google Cloud Run (Next.js backend) + Vercel (static frontend)
- **Database**: Cloud SQL PostgreSQL with connection pooling
- **Storage**: Cloud Storage for user uploads
- **CDN**: Cloudflare for static assets
- **Secrets**: Google Secret Manager

## Observability Stack

- **Logging**: Cloud Logging + structured JSON logs
- **Tracing**: OpenTelemetry → Cloud Trace
- **Metrics**: Prometheus + Grafana (or Cloud Monitoring)
- **Errors**: Sentry for error tracking
- **Uptime**: Uptime monitoring (Pingdom/UptimeRobot)

## Key Features

- Health check endpoint (`/api/health`)
- Database connection pooling (Prisma)
- Automated DB backups (daily snapshots)
- Rate limiting (Redis cache)
- CDN cache invalidation
- Rolling deployments with zero downtime
- Rollback plan

## Environment Variables

```
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
SENTRY_DSN=https://...
STRIPE_SECRET_KEY=sk_live_...
NEXTAUTH_URL=https://camarad.ai
```

## Testing

- [ ] Health checks pass
- [ ] Logs structured and searchable
- [ ] Errors reported to Sentry
- [ ] DB backups automated
- [ ] Rate limiting works
- [ ] SSL certificates valid
- [ ] DNS configured correctly
- [ ] Load testing passed (1000+ concurrent users)
