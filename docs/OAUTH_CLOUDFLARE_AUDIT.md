# OAuth + Cloudflare Cache Audit

Date: 2026-02-13

## Scope
This audit covers OAuth callback caching risk for Camarad connector flows.

## Required Cache Bypass Paths
- `/api/connectors/ga4/oauth/callback*`
- `/api/connectors/*/oauth/*`

These paths must bypass cache at edge even when global "Cache Everything" rules exist.

## Verification Commands
```bash
curl -I https://camarad.ai/api/connectors/ga4/oauth/callback | sed -n '1,25p'
curl -I https://camarad.ai/api/connectors/ga4/oauth/callback?x=1 | sed -n '1,25p'
```

## Expected Headers / Signals
- HTTP should be app-origin response class (typically `400` without OAuth params).
- `Cache-Control` must include `no-store` (or `no-cache` at minimum).
- Callback responses must not be cached by edge rules.

## Why Bypass Is Required
OAuth callbacks carry short-lived state and one-time code exchange behavior.
Caching callback paths can cause:
- stale state validation behavior,
- replay-like failures,
- intermittent 404/invalid state outcomes across edges.

Bypass on these paths keeps callback handling deterministic.
