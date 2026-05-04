# Google Ads MCC Hierarchy — Phase 2A.1 Audit

**Date**: 2026-05-04  
**Branch**: `feature/google-ads-mcc-hierarchy-2026-05-03`  
**Base**: `292507a` (API v20 fix on top of Phase 2A)

---

## 1. Current State

### Accounts Endpoint (`GET /api/connectors/google-ads/accounts`)

Three-tier logic:
1. `api_validated=True` → returns `google_ads_accessible_customers` DB table rows. `source="google_ads_api"`.
2. `has_token, not api_validated` → returns `{accounts: [], source: "none"}`. Correct — no mock.
3. Otherwise → Coolbits gateway proxy, then mock fallback (`source="coolbits"` or `source="mock"`).

**Problem**: In tier 1, the response only contains directly accessible accounts from `ListAccessibleCustomers`. These are not the same as MCC child accounts. The accounts are presented as "Client" type regardless of whether they are manager or client accounts. No hierarchy information.

### MCC Input/Filter (`gadsApplyMccId()`)

Current JS behavior:
- User types an MCC ID in `#gadsMccId` input and presses button or blurs.
- `gadsApplyMccId()` saves it to `gadsState.mccId` and calls `refreshAccounts(true)`.
- `refreshAccounts` re-fetches `/api/connectors/google-ads/accounts?mcc_id=<id>`.
- In `api_validated` tier, `mcc_id` query param is **ignored** — it only returns `google_ads_accessible_customers`.
- Toast fires: `"MCC filter applied: 123-456-7890"` — **misleading** because no real API call is made.
- In non-validated tier, `mcc_id` is forwarded to Coolbits gateway — this might work for legacy MCC proxying but is not a real customer_client query.

**Problems**:
- `"MCC filter applied"` toast implies something happened, but in live mode it does nothing.
- `bi-arrow-repeat` button icon implies "refresh" not "load hierarchy".
- No distinction between direct-access accounts and hierarchy accounts.
- No `customer_client` query to Google Ads API.
- No manager/client type classification from API.
- MCC input blurs trigger re-fetch even in live mode where the input is unused.

### DB Tables (current)

- `provider_credentials` — OAuth tokens, metadata (includes `api_validated`, `customer_id`, `login_customer_id`).
- `google_ads_accessible_customers` — Rows from `ListAccessibleCustomers`. Columns: `user_id, customer_id, resource_name, display_name, status, source, last_seen_at`.

**Missing**: No table for MCC hierarchy (customer_client result). No `is_manager`, `level`, `descriptive_name` from `customer_client`.

### UI Copy Issues

| Location | Current text | Problem |
|----------|-------------|---------|
| `#gadsDemoNotice` (connected_live) | hidden | OK |
| `#gadsDemoNotice` (token_stored) | "OAuth token stored. API validation pending." | OK |
| `#gadsDemoNotice` (oauth_required) | "Demo Data — Showing demo/mock..." | OK |
| MCC input button | `bi-arrow-repeat` | Misleading "refresh" icon for what should be "load hierarchy" |
| MCC toast | "MCC filter applied: X" | Misleading — no real hierarchy loaded |
| Account select label | "Account:" | Does not distinguish direct-access vs hierarchy |
| Account select options | all labeled "Client" | Wrong — some are managers |
| connected_live notice | nothing | No message telling user to load MCC hierarchy |

---

## 2. What Is Needed

### A. Real API: `customer_client` Query

Use GAQL `SearchStream` against a manager/MCC customer ID:

```
POST https://googleads.googleapis.com/v20/customers/{manager_customer_id}/googleAds:searchStream
Headers: Authorization, developer-token, login-customer-id
Body: {
  "query": "SELECT customer_client.client_customer, customer_client.id, customer_client.descriptive_name, customer_client.manager, customer_client.status, customer_client.level, customer_client.currency_code, customer_client.time_zone FROM customer_client WHERE customer_client.status IN ('ENABLED')"
}
```

Returns stream of JSON objects. Parse `results[*].customerClient`.

### B. New DB Table: `google_ads_customer_hierarchy`

Stores customer_client results per user + manager. Idempotent CREATE IF NOT EXISTS.

### C. Account Type Model

```
direct_access  — from ListAccessibleCustomers, type unknown until hierarchy query
manager        — customer_client.manager = true
client         — customer_client.manager = false
unknown        — fallback
```

### D. New Endpoints

- `POST /api/connectors/google-ads/mcc/hierarchy` — triggers real customer_client query, stores results.
- `GET /api/connectors/google-ads/mcc/hierarchy?manager_customer_id=X` — returns cached DB rows.
- Updated `GET /api/connectors/google-ads/accounts` — returns `direct_access_accounts` + `mcc_accounts` separately + `mcc_hierarchy_loaded` flag.

### E. UI Changes

- Replace "Account:" label + single select with two clearly labeled sections:
  1. **Directly Accessible Accounts** (from ListAccessibleCustomers)
  2. **MCC Manager Context** (input + "Load MCC Hierarchy" button)
  3. **Client Account** (select from hierarchy results)
- Remove `gadsApplyMccId()` and "MCC filter applied" toast.
- Add `gadsLoadMccHierarchy()` function.
- Update notice for `connected_live` state.

---

## 3. Risks / Blockers

| Risk | Mitigation |
|------|-----------|
| Manager account not in accessible customers | UI allows manual entry of manager_customer_id |
| `customer_client` returns 403 if token not approved for manager | Safe error message, no crash |
| SearchStream returns NDJSON not plain JSON | Parse line-by-line |
| `login-customer-id` header must equal manager for MCC traversal | Use manager_customer_id as login-customer-id header |
| Empty hierarchy (account is not manager) | Return safe `not_manager_or_no_children` error with empty list |
| Test accounts may not have hierarchy | Mocked in tests |

---

## 4. Tests to Add

File: `backend_py/test_google_ads_mcc_hierarchy.py`

15 required tests listed in spec. See test file for full coverage.

---

## 5. Files to Change

- `backend_py/app.py` — helpers + endpoints
- `backend_py/templates/connectors.html` — UI restructure
- `backend_py/test_google_ads_mcc_hierarchy.py` — new test file
