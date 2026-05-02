# Google Ads Truth Mode — Phase 1 Result
**Date**: 2026-05-03
**Branch**: feature/google-ads-truth-mode-2026-05-03
**Commit**: TBD

---

## Summary

Phase 1 truth mode successfully implemented. All data endpoints now accurately report
mock/demo status. UI no longer shows misleading green "Connected" badge or
"Connected successfully!" toast. No live OAuth or real API calls were made or planned.

## Deliverables

| Item | Status |
|---|---|
| `GET /api/connectors/google-ads/reality/status` | ✅ Implemented |
| Mock data endpoints — `connected_live: false` metadata | ✅ Implemented |
| Mock data endpoints — `connected_mock: true` metadata | ✅ Implemented |
| `test-call` — `api_validated: false` + `message` | ✅ Implemented |
| `gadsConnect()` — badge changed from "Connected" (green) to "Demo Data" (gray) | ✅ Fixed |
| `gadsConnect()` — toast changed from "Connected successfully!" to demo disclaimer | ✅ Fixed |
| `gadsInit()` — badge reads from `reality/status` `ui_label` | ✅ Fixed |
| Demo Data notice banner in Google Ads panel | ✅ Added |
| Test API JS — "Simulated response" warning in result | ✅ Added |
| `test_google_ads_truth_mode.py` — 10 tests | ✅ 10/10 pass |

## Test Results

```
Ran 10 tests in 0.054s
OK

Critical regression suites:
  test_flows_approval_dry_run — 14/14 OK
  test_flows_draft_mode — 8/8 OK
  test_mwr_landing — 2/2 OK
  test_ai_provider_policy — 7/7 OK
  Total: 37/37 OK
```

## Flask Smoke

All endpoints return expected values:
- `/api/connectors/google-ads/reality/status` → 200, `connected_live: false`, `api_validated: false`
- `/api/connectors/google-ads/accounts` → 200, `source: mock`, `connected_live: false`
- `/api/connectors/google-ads/campaigns` → 200, `source: mock`, `connected_live: false`
- `/api/connectors/google-ads/keywords` → 200, `source: mock`, `connected_live: false`
- `/api/connectors/google-ads/metrics` → 200, `source: mock`, `connected_live: false`
- `POST /api/connectors/google-ads/test-call` → 200, `source: mock`, `api_validated: false`

## Safety Constraints Met

- ✅ No real OAuth implemented
- ✅ No google-ads SDK installed
- ✅ No live Google Ads API calls
- ✅ Mock/demo data preserved
- ✅ Existing connector UI not broken
- ✅ Flows v2 tests still pass 14/14
- ✅ MWR/Vacante preserved
- ✅ No secrets printed/exposed
- ✅ DB not overwritten
- ✅ `.env` not modified

## What Changed

### `backend_py/app.py`
- `_google_ads_mock_accounts_response()` — added `connected_live`, `connected_mock`, `message`
- `_google_ads_mock_campaigns_response()` — added `connected_live`, `connected_mock`, `message`
- `_google_ads_mock_keywords_response()` — added `connected_live`, `connected_mock`
- `_google_ads_mock_metrics_response()` — added `connected_live`, `connected_mock`
- `google_ads_test_call()` — added `api_validated: False`, `message`
- NEW `google_ads_reality_status()` — `GET /api/connectors/google-ads/reality/status`

### `backend_py/templates/connectors.html`
- `gadsState` — added `reality: null` field
- `gadsInit()` — badge now driven by `reality/status` `ui_label` / `ui_badge_class`, never shows green for mock
- `gadsConnect()` — badge "Demo Data" (gray), toast is demo disclaimer, saves `connected_mock` status
- Google Ads panel — added `#gadsDemoNotice` banner
- Test API JS — added "Simulated response" warning in result output
