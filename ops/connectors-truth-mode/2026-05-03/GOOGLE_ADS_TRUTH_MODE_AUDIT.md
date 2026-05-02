# Google Ads Truth Mode — Pre-Implementation Audit
**Date**: 2026-05-03
**Branch**: feature/google-ads-truth-mode-2026-05-03
**Base commit**: ddb76c85e838033465b60a523fd77c40621141a2

---

## Routes Touched

| Route | File | Lines | Change |
|---|---|---|---|
| `GET /api/connectors/google-ads/reality/status` | app.py | NEW (~20258) | Add |
| `GET /api/connectors/google-ads/accounts` | app.py | ~19787 | Add metadata to mock response |
| `GET /api/connectors/google-ads/campaigns` | app.py | ~19813 | Add metadata to mock response |
| `GET /api/connectors/google-ads/keywords` | app.py | ~19865 | Add metadata to mock response |
| `GET /api/connectors/google-ads/metrics` | app.py | ~19915 | Add metadata to mock response |
| `GET /api/connectors/google-ads/reports` | app.py | ~20063 | Add metadata to mock fallback |
| `POST /api/connectors/google-ads/test-call` | app.py | ~20189 | Add api_validated=false + message |

## Current Mock Source

All data endpoints call `_google_ads_mock_*_response()` helper functions:
- `_google_ads_mock_accounts_response()` → GOOGLE_ADS_MOCK_ACCOUNTS (hardcoded)
- `_google_ads_mock_campaigns_response(account_id)` → GOOGLE_ADS_MOCK_CAMPAIGNS dict
- `_google_ads_mock_keywords_response(campaign_id)` → GOOGLE_ADS_MOCK_KEYWORDS dict
- `_google_ads_mock_metrics_response(account_id, days)` → random.seed(42) deterministic
- `google_ads_test_call()` → hardcoded fake Bearer token + responses (source: mock already)

## Current UI Badge Logic

In `gadsInit()` (connectors.html ~5540):
```js
badge.textContent = gadsState.connected ? 'Connected' : 'Disconnected';
badge.className = gadsState.connected ? 'badge bg-success' : 'badge bg-secondary';
```
Driven by `data.status === 'Connected'` from `GET /api/connectors/google-ads`.

In `gadsConnect()` (connectors.html ~5561):
```js
badge.textContent = 'Connected'; badge.className = 'badge bg-success';
window.showToast('Google Ads', 'Connected successfully! Loading account data...', 'success');
```
This is the fake connect — no OAuth.

## Exact Endpoint Plan

### `GET /api/connectors/google-ads/reality/status`
- Check env for `GOOGLE_ADS_CLIENT_ID`, `GOOGLE_ADS_CLIENT_SECRET`, `GOOGLE_ADS_DEVELOPER_TOKEN` — boolean only
- Check DB `oauth_states` for provider='google-ads' row — boolean only  
- Check DB `connectors_config.config_json` for oauth token keys — boolean only
- Return: provider, mode, connected_live=false, connected_mock=true, oauth_configured bool, has_token bool, token_validated=false, api_validated=false, customer_id=null, login_customer_id=null, data_source='mock', ui_label, ui_badge_class, message
- Never expose secret values

### Mock response helpers — add:
- `connected_live: false`
- `connected_mock: true`
- `message: "Demo data only. No live Google Ads OAuth connection is active."`

### test-call — add:
- `api_validated: false`
- `message: "Simulated Google Ads API response. No live API call was made."`

## Exact UI Label Plan

### Badge in gadsInit()
- Call `GET /api/connectors/google-ads/reality/status` on panel open
- Use `ui_label` from response for badge text
- Map `ui_badge_class`:
  - `demo` → `badge bg-secondary` (gray, never green)
  - `warning` → `badge bg-warning text-dark`
  - `success` → `badge bg-success` (only for true live)
  - `danger` → `badge bg-danger`
- Store reality data in `gadsState.reality`

### Demo Data notice banner
- `id="gadsDemoNotice"` div in panel
- Show when `gadsState.reality?.mode !== 'live'` or `connected_live !== true`
- Text: "Demo Data — Showing demo/mock Google Ads data. No live OAuth connection is active."

### gadsConnect() fix
- Badge text: "Demo Data" (not "Connected")
- Badge class: `badge bg-secondary` (not `bg-success`)
- Toast: "Demo mode active. No Google Ads OAuth connection was made." (not "Connected successfully!")
- Save status as 'connected_mock' to DB (not 'Connected')

### Test API JS
- Add "Simulated" label after the response card
- Show: "⚠️ Simulated response — No live Google Ads API call was made."

## Tests to Add

File: `backend_py/test_google_ads_truth_mode.py`

1. reality/status returns mode=mock/config_missing in default config
2. reality/status never includes actual secret values in response
3. accounts returns source=mock, connected_live=false
4. campaigns returns source=mock, connected_live=false
5. keywords returns source=mock, connected_live=false
6. metrics returns source=mock, connected_live=false
7. test-call returns source=mock, api_validated=false, message contains "Simulated"/"No live"
8. connectors_config.status='Connected' without token → reality/status returns connected_mock=true, connected_live=false
9. oauth_states empty → has_token=false
10. No secret field names in reality/status response

## Safety Constraints

- `reality/status` must never print token values, only booleans
- `reality/status` must never call Google Ads API
- Mock data remains available — no data removal
- `connected_live=true` only allowed if token + API validated (Phase 3)
- `ui_badge_class='success'` only allowed for `connected_live=true`
- All test API console outputs labeled as simulated
- Connect button no longer says "Connected successfully" for mock state
