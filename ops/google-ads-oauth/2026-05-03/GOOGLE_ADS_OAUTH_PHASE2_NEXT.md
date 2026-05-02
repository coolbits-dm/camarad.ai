# Google Ads OAuth Phase 2 — Next Steps

## What Phase 2 Must Add

### 1. `ListAccessibleCustomers` API Call
When validate is triggered, call Google Ads API v17:
```
GET https://googleads.googleapis.com/v17/customers:listAccessibleCustomers
Authorization: Bearer <fresh_access_token>
developer-token: <GOOGLE_ADS_DEVELOPER_TOKEN>
```
On success: set `api_validated=True`, `connected_live=True` in `provider_credentials.metadata_json`.

### 2. Token Refresh Before API Call
Before calling the API, always refresh the access token:
```
POST https://oauth2.googleapis.com/token
{client_id, client_secret, refresh_token, grant_type=refresh_token}
```
If refresh fails (400/401): set `token_validated=False`, `api_validated=False` in metadata.

### 3. Customer ID Storage
After `ListAccessibleCustomers` returns, store the first accessible `customer_id` in `metadata_json`.
If `GOOGLE_ADS_LOGIN_CUSTOMER_ID` is set, use it as the login customer.

### 4. `connected_live=True` Route Update
In `google_ads_reality_status()`, `connected_live=True` when `api_validated=True` AND `token_validated=True`.
Phase 2 must wire this by calling `_gads_validate_token()` from `google_ads_validate()`.

### 5. Real Accounts Endpoint
Replace mock in `GET /api/connectors/google-ads/accounts`:
```
GET https://googleads.googleapis.com/v17/customers/{login_customer_id}/googleAds:search
Query: SELECT customer.id, customer.descriptive_name, customer.currency_code, customer.time_zone
       FROM customer
       WHERE customer.manager = false LIMIT 50
```

### 6. Token Auto-Refresh Middleware
Add `_gads_get_fresh_access_token(user_id)` helper that:
1. Reads `secret_encrypted` → decrypts → gets `refresh_token`
2. POSTs to token endpoint
3. Returns fresh `access_token` (never stored)
4. On failure: sets `token_validated=False` in metadata

### 7. `gadsValidateToken()` Backend Completeness
Current Phase 1 `google_ads_validate()` only checks token presence.
Phase 2 must call `_gads_validate_token()` which calls the API.

---

## Env Vars to Set in Production for Phase 2

```bash
GOOGLE_ADS_CLIENT_ID=<from GCP console>
GOOGLE_ADS_CLIENT_SECRET=<from GCP console>
GOOGLE_ADS_DEVELOPER_TOKEN=<from Google Ads Manager Account>
GOOGLE_ADS_REDIRECT_URI=https://camarad.ai/api/connectors/google-ads/oauth/callback
# Optional:
GOOGLE_ADS_LOGIN_CUSTOMER_ID=<MCC account ID if applicable>
```

## GCP Console Setup Required

1. Create OAuth 2.0 Client ID (Web application) in GCP console
2. Add authorized redirect URI: `https://camarad.ai/api/connectors/google-ads/oauth/callback`
3. Enable Google Ads API in GCP project
4. Apply for Developer Token in Google Ads Manager Account
5. Set test users in OAuth consent screen (until app is verified)

## Phase 2 Tests to Add

- `test_gads_token_refresh_success` — mock token endpoint 200, verify fresh token not stored
- `test_gads_token_refresh_failure_marks_invalid` — mock 401, verify metadata updated
- `test_gads_list_accessible_customers_success` — mock API 200, verify api_validated=True
- `test_gads_list_accessible_customers_auth_fail` — mock API 401, verify connected_live=False
- `test_gads_validate_sets_connected_live` — full flow mock, verify reality/status returns connected_live=True
- `test_gads_real_accounts_endpoint` — verify /accounts returns live data when connected_live

## Notes

- Phase 1 is deployed with `connected_live=False` always. Safe.
- Phase 2 is blocked by: env vars in prod + GCP OAuth app setup + Google Ads Developer Token approval.
- No code changes needed in `provider_credentials` or `oauth_states` tables.
- Do NOT install `google-ads` SDK — continue using `requests` directly.
