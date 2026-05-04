# Google Ads API Validation — Phase 2A Result

**Date**: 2026-05-04  
**Branch**: `feature/google-ads-api-validation-2026-05-03`  
**Base**: `1b78bea` (Google Ads OAuth Phase 1)

---

## Status: IMPLEMENTED ✅

---

## Endpoint Changes

### `POST /api/connectors/google-ads/validate` — REWRITTEN
**Before (Phase 1)**: Token presence check only. Always returned `token_stored` stub.  
**After (Phase 2A)**: Full real API validation.

Flow:
1. Config check → 400 `config_missing` if missing.
2. Token presence check → 400 `oauth_required` if no active token.
3. `_gads_get_fresh_access_token(user_id)` → refreshes via `oauth2.googleapis.com/token`.
4. `_gads_list_accessible_customers(access_token, developer_token)` → `GET googleads.googleapis.com/v17/customers:listAccessibleCustomers`.
5. `_gads_store_accessible_customers(user_id, customer_ids)` → upserts to `google_ads_accessible_customers` table.
6. `_gads_update_metadata(...)` → sets `api_validated=True`, `last_validated_at`, `customer_id`.
7. Returns: `{ success: true, connected_live: true, accessible_customers_count: N, customers: [...] }`.

### `GET /api/connectors/google-ads/reality/status` — UPDATED
- Added `accessible_customers_count` field (populated when `connected_live=true`).
- `data_source` now `"google_ads_api"` (was `"live"`) when connected.
- `token_stored` message updated: "OAuth token stored. API validation pending."
- `connected_live` message updated: "Live Google Ads account access validated."
- `connected_mock=True` preserved during `token_stored` (demo still available).

### `GET /api/connectors/google-ads/accounts` — UPDATED
- **connected_live**: Returns real accessible customers from `google_ads_accessible_customers` DB table. `source="google_ads_api"`.
- **token_stored**: Returns empty list with message "Validate Google Ads API access to load accounts." No mock E-Shop.
- **config_missing / oauth_required**: Returns mock (Coolbits gateway or fallback mock) as before.

### `POST /api/connectors/google-ads/test-call` — UPDATED
- Checks `api_validated` from metadata. If validated: `source="simulated"`, message mentions Phase 2B campaign deferral. If not: `source="mock"`, message says "API validation pending."

---

## New Helpers

| Helper | Purpose |
|--------|---------|
| `_gads_update_metadata(user_id, updates)` | Merge updates into `provider_credentials.metadata_json` |
| `_gads_get_fresh_access_token(user_id)` | Decrypt stored refresh_token, POST to Google token endpoint, return access_token |
| `_gads_list_accessible_customers(access_token, developer_token)` | GET ListAccessibleCustomers REST call |
| `_gads_store_accessible_customers(user_id, customer_ids)` | Upsert customer IDs to `google_ads_accessible_customers` |
| `_gads_get_accessible_customers(user_id)` | Read active customers from DB for user |

### Constants added
```python
_GADS_API_VERSION = "v17"
_GADS_API_BASE = "https://googleads.googleapis.com"
```

---

## DB Table: `google_ads_accessible_customers`

Created via `CREATE TABLE IF NOT EXISTS` inside `_gads_store_accessible_customers`.

```sql
CREATE TABLE IF NOT EXISTS google_ads_accessible_customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    customer_id TEXT NOT NULL,
    resource_name TEXT NOT NULL,
    display_name TEXT,
    status TEXT NOT NULL DEFAULT 'accessible',
    source TEXT NOT NULL DEFAULT 'google_ads_api',
    last_seen_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, customer_id)
)
```

Upsert logic: before each fresh sync, all existing rows for the user are marked `status='not_seen'`. Fresh batch is inserted/updated as `status='accessible'`.

---

## Token Refresh Behavior

1. Read `secret_encrypted` from `provider_credentials`.
2. Decrypt with `_decrypt_provider_secret()` → JSON payload → extract `refresh_token`.
3. POST to `https://oauth2.googleapis.com/token` with `grant_type=refresh_token`.
4. On 200: return `access_token` (never stored, never logged).
5. On non-200: update `token_validated=False, api_validated=False` in metadata. Return safe error.
6. Never log or return `refresh_token`, `client_secret`, `developer_token`, or `access_token`.

---

## UI State Changes

| Mode | Before | After |
|------|--------|-------|
| `token_stored` | Demo notice: "No live OAuth connection is active" (wrong) | Info notice: "OAuth token stored. API validation pending. Click Validate Access." |
| `token_stored` | Demo notice class: `alert-secondary` | Notice class: `alert-info` |
| `connected_live` | Demo notice hidden | Demo notice hidden |
| `oauth_required` | Demo notice: generic | Demo notice: links to OAuth start |
| `gadsValidateToken()` | No spinner | Shows spinner + "Validating..." during call |
| `gadsValidateToken()` | Calls `gadsInit()` | Calls `await gadsInit()` (async, refreshes accounts) |

---

## Security Properties

- Access token is never stored in DB.
- Access token is never returned in any API response.
- Refresh token is only stored encrypted (Fernet). Never returned.
- Developer token is never returned in any response.
- `_gads_list_accessible_customers` return value never includes headers or tokens.
- Google Ads API error responses are truncated to 300 chars and sanitized before returning.
- No write/mutation API calls made during validation.

---

## Tests

**File**: `backend_py/test_google_ads_api_validation.py`  
**Tests**: 26/26 pass.

| Class | Tests |
|-------|-------|
| `TestValidateWithoutToken` | 1 |
| `TestValidateMissingConfig` | 1 |
| `TestTokenRefresh` | 2 |
| `TestListAccessibleCustomersHeaders` | 1 |
| `TestAccessibleCustomersStorage` | 1 |
| `TestValidationSetsConnectedLive` | 1 |
| `TestRealityStatusConnectedLive` | 2 |
| `TestAccountsEndpoint` | 1 |
| `TestTokenStoredNoMockEShop` | 1 |
| `TestFailedApiResponseError` | 1 |
| `TestUiTemplateMessages` | 2 |
| `TestNoSecretsInResponses` | 3 |
| `TestTestCallSimulated` | 2 |
| `TestNoMutationEndpointCalled` | 1 |
| `TestGadsListAccessibleCustomersHelper` | 3 |
| `TestGadsStoreAccessibleCustomers` | 3 |

**Broader suite**: 66 Google Ads tests pass (26 Phase 2A + 30 Phase 1 + 10 truth-mode). 51 other tests (flows, chat hardening, AI provider, MWR) pass. Conversation brief tests pass.

---

## What Remains (Phase 2B)

- Campaign read-only GAQL query per selected customer_id.
- Account selector → campaign data flow.
- Token auto-refresh before each API call (currently refreshed only at validate time).
- Caching of validated accessible customers (TTL).
- `connected_live` campaigns tab (currently shows deferred message).
- Flows v3 adapters reading from live Google Ads data.
- Login customer ID selection for MCC accounts.

---

## Deploy Recommendation

Safe to deploy. Requires:
1. Production env already configured (done 2026-05-04).
2. `pm2 restart camarad --update-env` after rsync.
3. Browser validate click to trigger `ListAccessibleCustomers` and set `connected_live=true`.
4. No schema migration needed — `google_ads_accessible_customers` created via `CREATE TABLE IF NOT EXISTS`.
