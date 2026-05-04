# MCC UI Mapping Bug — Audit

**Date**: 2026-05-04  
**Branch**: `feature/google-ads-mcc-ui-mapping-fix-2026-05-04`  
**Base**: `42004e5` (JSON array parsing fix)  
**Severity**: High — live users saw direct-access accounts instead of MCC client accounts  

---

## Symptom

After clicking "Load MCC Hierarchy" (which correctly fetched and stored 19 accounts: 1 manager, 18 clients), the **Client Account dropdown still showed the 3 directly accessible accounts** (ListAccessibleCustomers) instead of the 18 MCC client accounts.

---

## Root Cause Analysis

### Root Cause A — Primary (backend): `_gads_token_get_meta` truncated return dict

`_gads_token_get_meta()` returns a hardcoded subset of metadata fields. `selected_manager_customer_id` was **not included** in the return dict.

**Consequence chain:**
1. `google_ads_mcc_hierarchy_load()` POST calls `_gads_update_metadata(user_id, {"selected_manager_customer_id": manager_customer_id})` — correctly stores it.
2. `google_ads_accounts()` GET reads `meta = _gads_token_get_meta(user_id)`, then does `selected_manager = str((meta or {}).get("selected_manager_customer_id") or "")`.
3. Since `_gads_token_get_meta` never returns `selected_manager_customer_id`, `selected_manager` is always `""`.
4. The `if selected_manager:` branch is never taken → `mcc_accounts = []`, `mcc_hierarchy_loaded = False`.
5. Frontend receives `mcc_accounts: []` → `clientAccounts = []`.
6. Fallback to `gadsState.directAccessAccounts` activates.

### Root Cause B — Secondary (frontend): Fallback populates dropdown even with placeholder

In `refreshAccounts()`, when `clientAccounts.length === 0`:
```javascript
gadsState.accounts = clientAccounts.length ? ...
  : gadsState.directAccessAccounts.map(normalizeGadsAccount).filter(Boolean);
sel.innerHTML = '— Load MCC Hierarchy first —';
gadsState.accounts.forEach(a => { ... sel.appendChild(opt); });  // BUG: still runs!
```
The placeholder HTML is set, but then `gadsState.accounts` (direct accounts) are still appended as options.

### Root Cause C — Missing response fields

POST `/mcc/hierarchy` and GET `/accounts` did not return explicit `client_accounts` / `manager_accounts` arrays. The frontend had to filter `mcc_accounts` by `is_manager`, which only worked after Root Cause A was fixed.

---

## Fixes Applied

| # | File | Change |
|---|------|--------|
| A | `backend_py/app.py` | `_gads_token_get_meta`: add `"selected_manager_customer_id": meta.get("selected_manager_customer_id")` to return dict |
| B | `backend_py/app.py` | `google_ads_mcc_hierarchy_load()`: add `client_accounts` and `manager_accounts` to response |
| C | `backend_py/app.py` | `google_ads_mcc_hierarchy_get()`: add `client_accounts` and `manager_accounts` to response |
| D | `backend_py/app.py` | `google_ads_accounts()`: add `client_accounts` and `manager_accounts` to `api_validated` response |
| E | `backend_py/templates/connectors.html` | `refreshAccounts()`: use `data.client_accounts` if present; in live mode with no clients, set `gadsState.accounts = []` (no fallback to direct accounts) |
| F | `backend_py/templates/connectors.html` | `refreshAccounts()`: `gadsState.directAccessAccounts` never falls back to `allAccounts` in live mode |
| G | `backend_py/templates/connectors.html` | `gadsLoadMccHierarchy()`: immediately populate client dropdown from POST `data.client_accounts` before `refreshAccounts(true)` |

---

## Hard Constraints Maintained

- No `cat .env`, no secret values in logs or responses
- No Google Ads write/mutation APIs
- No campaign data (Phase 2B deferred)
- `re`, `json`, `requests` already imported in app.py — no new imports needed
- No `git add .` — explicit adds only
- No `rsync --delete`
