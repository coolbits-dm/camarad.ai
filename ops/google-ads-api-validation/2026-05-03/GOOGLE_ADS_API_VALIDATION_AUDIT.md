# Google Ads API Validation — Phase 2A Audit

**Date**: 2026-05-04  
**Branch**: `feature/google-ads-api-validation-2026-05-03`  
**Base commit**: `1b78bea` (Google Ads OAuth Phase 1)

---

## Current State (Phase 1, as deployed)

### `POST /api/connectors/google-ads/validate`
- Returns immediately if config missing → 400 `config_missing`.
- Returns immediately if no active token → 400 `oauth_required`.
- If token present: returns `{ success: true, status: "token_stored", api_validated: false, connected_live: false }`.
- **No real API call is made.**
- Phase 1 stub message: "Token stored. Full API validation (connected_live=true) requires Phase 2."

### `GET /api/connectors/google-ads/reality/status`
- Reads `provider_credentials` row for user.
- `connected_live = api_validated` (from metadata_json).
- Since `api_validated` is never set `True` in Phase 1, `connected_live` is always `False`.
- Modes: `config_missing` / `oauth_required` / `token_stored` / `connected_live`.
- `token_stored` message: "OAuth token stored. Click 'Validate Access' to confirm the connection. Demo data shown until validated."

### `GET /api/connectors/google-ads/accounts`
- If Coolbits gateway enabled: tries gateway paths. Falls through to mock.
- Returns `_google_ads_mock_accounts_response()` when gateway fails or disabled.
- Mock message: "Demo Data only. No live Google Ads OAuth connection is active."
- Does NOT check OAuth token status. Returns mock regardless.

### `_gads_token_store(user_id, token_data)`
- Stores `{ refresh_token, token_type }` encrypted via Fernet in `provider_credentials.secret_encrypted`.
- Metadata: `{ scopes, customer_id: null, login_customer_id, token_validated: true, api_validated: false, last_validated_at: null }`.

### `_gads_token_get_meta(user_id)`
- Returns metadata dict: `{ status, token_validated, api_validated, customer_id, login_customer_id, scopes, last_validated_at, updated_at }`.
- Never returns secret_encrypted content.

### Token Refresh
- **Not implemented in Phase 1.**
- `_gads_oauth_config_internal()` has `client_id`, `client_secret`, `redirect_uri` but no refresh helper.

### Accessible Customers Storage
- **No DB table for accessible customers.**
- `metadata_json.customer_id` can hold a single ID but no list.

### UI State (connectors.html)
- `token_stored` mode: shows "Validate Access" + "Disconnect" buttons.
- `gadsValidateToken()`: POSTs to `/api/connectors/google-ads/validate`, then calls `gadsInit()`.
- Demo notice (`#gadsDemoNotice`): hidden only if `connected_live === true`.
- **Bug**: Demo notice says "No live OAuth connection is active" even in `token_stored` mode, which is confusing.
- `connected_live` mode: shows only "Disconnect" button. Demo notice hidden.

### `POST /api/connectors/google-ads/test-call`
- Fully simulated. Returns mock response with `api_validated: false`.
- Does not check actual token state.

---

## Risks / Blockers

1. **Access token expiry**: Phase 1 stores refresh_token but never refreshes. Must refresh before API call.
2. **Fernet key consistency**: Token encrypted at callback time with the key derived from env. If key changes between store and retrieve, decrypt will fail silently (returns ""). Must handle gracefully.
3. **requests library**: Available (`requests 2.31.0`). Can use for REST calls. No SDK needed.
4. **Developer token approval**: Google Ads developer tokens start in "test" mode, which can only access test accounts. If the account isn't a test account, calls may return `DEVELOPER_TOKEN_NOT_APPROVED`. Must handle gracefully with a safe error message (no token exposed).
5. **`connected_mock` must stay true** during `token_stored` so demo data continues to show. Only `connected_live` changes.

---

## Implementation Plan

### A. New constant
```python
_GADS_API_VERSION = "v17"
_GADS_API_BASE = "https://googleads.googleapis.com"
```

### B. `_gads_get_fresh_access_token(user_id)` helper
- Read `secret_encrypted` from `provider_credentials` for the user.
- Decrypt → parse JSON → extract `refresh_token`.
- If no refresh_token: return `{"success": False, "error": "no_refresh_token"}`.
- POST to `_GADS_TOKEN_ENDPOINT` with `grant_type=refresh_token`.
- On success: return `{"success": True, "access_token": <token>}` (never store access_token).
- On failure: update `token_validated=False` in metadata. Return `{"success": False, "error": "token_refresh_failed", "message": safe_msg}`.

### C. `_gads_list_accessible_customers(access_token, developer_token)` helper
- GET `https://googleads.googleapis.com/v17/customers:listAccessibleCustomers`.
- Headers: `Authorization: Bearer <access_token>`, `developer-token: <developer_token>`.
- On 200: parse `resourceNames`, extract customer IDs.
- Return: `{"success": True, "customer_resource_names": [...], "customer_ids": [...], "count": N}`.
- On error: return `{"success": False, "error": "google_ads_api_error", "status_code": N, "message": safe_msg}`.
- Never include access_token, developer_token, or raw Google error body (may contain sensitive info).

### D. `_gads_store_accessible_customers(user_id, customer_ids)` helper
- Create table `google_ads_accessible_customers` if not exists.
- Upsert each customer_id.
- Mark all previous rows for the user as `status='not_seen'` before inserting fresh batch.
- Return count stored.

### E. `_gads_update_metadata(user_id, updates)` helper
- Read existing metadata_json from `provider_credentials`.
- Merge `updates` dict.
- Write back.
- Keeps `CREATE TABLE IF NOT EXISTS` guard.

### F. Rewrite `google_ads_validate()`
- Step 1: Check config. Return 400 if missing.
- Step 2: Check token. Return 400 if no active token.
- Step 3: Call `_gads_get_fresh_access_token(user_id)`.
- Step 4: Call `_gads_list_accessible_customers(access_token, developer_token)`.
- Step 5: Store accessible customers.
- Step 6: Update metadata: `api_validated=True`, `last_validated_at=now`, `customer_id=first_id`.
- Step 7: Return safe success response with customer list.
- On any error: update metadata accordingly, return safe error response.

### G. Update `google_ads_reality_status()`
- Add `accessible_customers_count` to `connected_live` response.
- Fix `connected_mock` for `token_stored` — keep `True` (demo still available).
- Keep current mode logic.

### H. Update `google_ads_accounts()`
- Check reality status first.
- If `connected_live`: query `google_ads_accessible_customers` table, return real IDs.
- If `token_stored`: return empty list with message "Validate Access to load accounts."
- If `config_missing`/`oauth_required`: return mock (gateway or mock).
- Do NOT return mock E-Shop account when token_stored or connected_live.

### I. Update `google_ads_test_call()`
- If `api_validated=True`: return latest accessible customers from DB (not live call).
- If not: return `simulated=True`, `api_validated=False`, `message="Simulated..."`.

### J. UI fixes (connectors.html)
1. Fix `#gadsDemoNotice` text for `token_stored` mode.
2. Update `gadsValidateToken()` to show spinner during validation.
3. Add connected_live account population from API response.
4. Show campaigns deferred message when connected_live.

---

## Tests to Add (test_google_ads_api_validation.py)

14 tests covering:
1. validate without token → oauth_required
2. validate missing developer token → config_missing  
3. validate refreshes token (mocked)
4. validate headers sent correctly (mocked, values not printed)
5. successful ListAccessibleCustomers → stores customers
6. successful validation → api_validated=true, connected_live=true
7. reality/status → connected_live only after api_validated
8. accounts → source=google_ads_api after validation
9. token_stored → no mock E-Shop account in live path
10. failed API response → api_error, connected_live=false
11. UI template contains token_stored pending message
12. no response includes secrets
13. test-call in token_stored → simulated message
14. no mutation endpoint called
