# Google Ads OAuth Phase 1 — Pre-Implementation Audit
**Date**: 2026-05-03
**Branch**: feature/google-ads-oauth-phase1-2026-05-03
**Base commit**: 89234113413106664b7f43e7998cc34f95473aad (truth mode)

---

## Existing Google Ads Routes

| Route | File | Notes |
|---|---|---|
| `GET /api/connectors/google-ads/accounts` | app.py ~19787 | mock fallback |
| `GET /api/connectors/google-ads/campaigns` | app.py ~19813 | mock fallback |
| `GET /api/connectors/google-ads/keywords` | app.py ~19865 | mock fallback |
| `GET /api/connectors/google-ads/metrics` | app.py ~19915 | mock fallback |
| `POST /api/connectors/google-ads/generate-assets` | app.py ~19960 | always mock |
| `GET /api/connectors/google-ads/reports` | app.py ~20063 | mock fallback |
| `POST /api/connectors/google-ads/test-call` | app.py ~20189 | always mock, api_validated=false |
| `GET /api/connectors/google-ads/reality/status` | app.py ~20285 | added in truth mode |

## Existing Token/Credential Tables

### `provider_credentials` (REUSE — has Fernet encryption)
- `user_id`, `client_id`, `workspace_slug`, `provider_slug` — unique key
- `mode` — `byok` | `oauth` | etc.
- `secret_encrypted` — Fernet(PROVIDER_CREDENTIALS_SECRET)-encrypted blob
- `status` — `active` | `revoked` | etc.
- `metadata_json` — free-form dict
- Encryption helpers: `_encrypt_provider_secret()`, `_decrypt_provider_secret()`
- Used for AI provider keys today; reusing for Google Ads OAuth token JSON

### `oauth_states` (REUSE — already exists for GA4)
- `id`, `provider`, `state`, `user_id`, `workspace_id`, `redirect_uri`
- `created_at`, `expires_at`, `used_at`, `meta_json`
- Functions: `_ensure_oauth_states_table()`, `_ga4_store_oauth_state()` → replicated for google-ads

**Decision: Reuse both tables. No new schema needed.**

## Encryption Helpers Available

`_encrypt_provider_secret(raw)` — Fernet encrypt via `PROVIDER_CREDENTIALS_SECRET` env var  
`_decrypt_provider_secret(enc)` — Fernet decrypt (used only server-side, never returned to client)  
Fallback to `dev-provider-credentials-secret` if env var missing (deterministic dev key).

## OAuth Token Storage Strategy

For Google Ads OAuth token:
- `provider_credentials` row with `provider_slug='google-ads'`, `mode='oauth'`
- `secret_encrypted` = Fernet-encrypted JSON: `{access_token, refresh_token, expires_in, token_type}`
- `metadata_json` = `{scopes, customer_id, login_customer_id, token_validated, api_validated, last_validated_at}`
- `status` = `'active'` | `'revoked'`
- Refresh token stored but access token never returned to client
- `connected_live=true` only after `api_validated=true` (Phase 2)

## Env Var Detection Strategy

Boolean presence check only. Never print values:
```python
bool(os.getenv("GOOGLE_ADS_CLIENT_ID", "").strip()
     and os.getenv("GOOGLE_ADS_CLIENT_SECRET", "").strip()
     and os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "").strip())
```

## OAuth Endpoints to Add

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/connectors/google-ads/oauth/start` | GET | Generate state, return authorize_url |
| `/api/connectors/google-ads/oauth/callback` | GET | Validate state, exchange code, store token |
| `/api/connectors/google-ads/oauth/disconnect` | POST | Revoke token locally |
| `/api/connectors/google-ads/oauth/status` | GET | Return OAuth status (no secrets) |
| `/api/connectors/google-ads/validate` | POST | Check token, defer API validation to Phase 2 |

## Callback Security / State Strategy

- State = `hashlib.sha256(os.urandom(32)).hexdigest()` — 256 bits of entropy
- TTL = 600 seconds (10 minutes)
- State stored in `oauth_states` table with `provider='google-ads'`
- Callback validates: state exists, not expired, not consumed
- State marked consumed on first use (single-use)
- Code never logged or returned in any response
- Token response never forwarded to client

## Reality/Status Modes After Phase 1

| Condition | mode | ui_label | ui_badge_class |
|---|---|---|---|
| No OAuth config | `config_missing` | Config Missing | warning |
| Config present, no token | `oauth_required` | OAuth Required | warning |
| Token stored, not API validated | `token_stored` | Token Stored | warning |
| Token + API validated | `connected_live` | Live Connected | success |

## Tests to Add

`backend_py/test_google_ads_oauth_phase1.py` — 13 required tests:
1. oauth/start config_missing → 400
2. oauth/start with config → returns authorize_url + state
3. authorize_url does not contain client_secret
4. callback invalid state → redirect with error reason
5. callback expired state → redirect with error reason
6. callback consumed state → redirect with error reason
7. token storage never appears in status/reality responses
8. oauth/status no token → oauth_required
9. reality/status transitions (4 states)
10. disconnect marks token revoked
11. no route exposes access_token/refresh_token/client_secret
12. validate without token → oauth_required
13. validate does not perform mutations (read-only)

## Risks / Blockers

- **No `GOOGLE_ADS_CLIENT_ID` in prod env**: OAuth start returns 400. No blocker — deploy is safe.
- **Token exchange requires real Google auth flow**: Tests mock the token exchange — no real OAuth called in tests.
- **`api_validated` stays false in Phase 1**: `connected_live` stays false. `ListAccessibleCustomers` deferred to Phase 2.
- **Fernet key drift in dev**: `dev-provider-credentials-secret` deterministic fallback — tokens stored in test DB decrypt correctly in same process.
